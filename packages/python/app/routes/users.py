# users.py

# Standard library imports
import logging
import re
from datetime import datetime, UTC
from typing import List, Optional

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from pydantic import BaseModel
from bcrypt import hashpw, gensalt

# Local imports
import analytiq_data as ad
from app import users, limits
from analytiq_data.org_permissions import (
    BUILTIN_ADMIN,
    build_member_entry,
    builtin_permission_groups_document,
    member_has_admin_group,
    mongo_elem_match_org_admin,
)
from app.auth import (
    SYSTEM_ROLE_SYSADMIN,
    get_current_user,
    get_admin_user,
    is_organization_admin,
    is_system_admin,
    user_document_is_sysadmin,
    users_share_organization,
)
from app.models import User
from app.routes.payments import sync_customer, delete_payments_customer

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
users_router = APIRouter()

# User models
class UserCreate(BaseModel):
    email: str
    name: str
    password: str

class UserUpdate(BaseModel):
    name: str | None = None
    password: str | None = None
    is_sysadmin: bool | None = None
    email_verified: bool | None = None
    has_seen_tour: bool | None = None

class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    is_sysadmin: bool
    email_verified: bool | None
    created_at: datetime
    has_password: bool
    has_seen_tour: bool | None = None

class ListUsersResponse(BaseModel):
    users: List[UserResponse]
    total_count: int
    skip: int


def _user_document_to_response(user: dict) -> UserResponse:
    """Map a MongoDB user document to API response (tolerates missing/null email)."""
    email = user.get("email")
    if not email:
        logger.warning(f"User {user.get('_id')} has no email in database")
        email = ""
    return UserResponse(
        id=str(user["_id"]),
        email=email,
        name=user.get("name"),
        is_sysadmin=user_document_is_sysadmin(user),
        email_verified=user.get("email_verified"),
        created_at=user.get("created_at", datetime.now(UTC)),
        has_password=bool(user.get("password")),
        has_seen_tour=user.get("has_seen_tour"),
    )


# User endpoints
@users_router.get("/v0/account/users", response_model=ListUsersResponse, tags=["account/users"])
async def list_users(
    organization_id: str | None = Query(None, description="Filter users by organization ID"),
    user_id: str | None = Query(None, description="Get a specific user by ID"),
    search_name: str | None = Query(None, description="Case-insensitive search in name or email"),
    skip: int = Query(0, description="Number of users to skip"),
    limit: int = Query(10, description="Number of users to return"),
    current_user: User = Depends(get_current_user)
):
    """
    List users or get a specific user.
    - If user_id is provided, returns just that user (requires proper permissions)
    - If organization_id is provided, returns users from that organization
    - Otherwise returns all users (admin only)
    - user_id and organization_id are mutually exclusive
    """
    logger.debug(f"list_users(): organization_id: {organization_id} user_id: {user_id} current_user: {current_user} skip: {skip} limit: {limit}")
    
    db = ad.common.get_async_db()
    is_sys_admin = await is_system_admin(current_user.user_id)

    # user_id and organization_id are mutually exclusive
    if user_id and organization_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both user_id and organization_id"
        )

    # Build filters and compose final query at the end
    and_filters = []
    
    # Handle single user request
    if user_id:
        try:
            user = await db.users.find_one({"_id": ObjectId(user_id)})
        except:
            raise HTTPException(status_code=404, detail="User not found")
            
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check permissions
        is_self = current_user.user_id == user_id
        
        if not (is_sys_admin or is_self):
            can_view = await users_share_organization(current_user.user_id, user_id)
            if not can_view:
                # Org admins may view profiles of members in orgs they administer
                user_orgs = await db.organizations.find({
                    "members.user_id": user_id
                }).to_list(None)

                for org in user_orgs:
                    if await is_organization_admin(str(org["_id"]), current_user.user_id):
                        can_view = True
                        break

            if not can_view:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to view this user"
                )
                
        ret = ListUsersResponse(
            users=[_user_document_to_response(user)],
            total_count=1,
            skip=0
        )
        return ret

    # Handle organization filter
    if organization_id:
        org = await db.organizations.find_one({"_id": ObjectId(organization_id)})
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
            
        is_org_admin = await is_organization_admin(organization_id, current_user.user_id)
        
        if not (is_sys_admin or is_org_admin):
            raise HTTPException(
                status_code=403, 
                detail="Not authorized to view organization users"
            )
            
        member_ids = [m["user_id"] for m in org["members"]]
        and_filters.append({"_id": {"$in": [ObjectId(uid) for uid in member_ids]}})
    elif not is_sys_admin:
        # List all users in organizations the current user is an admin of
        orgs = await db.organizations.find(
            mongo_elem_match_org_admin(current_user.user_id)
        ).to_list(None)
        member_ids = [m["user_id"] for org in orgs for m in org["members"]]
        
        # Add the current user to the list of users, if they are not already in the list
        if current_user.user_id not in member_ids:
            member_ids.append(current_user.user_id)
        
        and_filters.append({"_id": {"$in": [ObjectId(uid) for uid in member_ids]}})
    else:
        # A system admin can list all users. No need to filter by organization.
        pass

    # Apply search_name filter if provided (search across entire user collection)
    if search_name:
        if len(search_name) > limits.MAX_SEARCH_TERM_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"search_name exceeds maximum length of {limits.MAX_SEARCH_TERM_LENGTH}",
            )
        escaped_search_name = re.escape(search_name)
        or_filter = {
            "$or": [
                {"name": {"$regex": escaped_search_name, "$options": "i"}},
                {"email": {"$regex": escaped_search_name, "$options": "i"}},
            ]
        }
        and_filters.append(or_filter)

    final_query = {"$and": and_filters} if and_filters else {}

    total_count = await db.users.count_documents(final_query)
    users = await db.users.find(final_query).skip(skip).limit(limit).to_list(None)

    ret = ListUsersResponse(
        users=[_user_document_to_response(user) for user in users],
        total_count=total_count,
        skip=skip
    )
    return ret

@users_router.post("/v0/account/users", response_model=UserResponse, tags=["account/users"])
async def create_user(
    user: UserCreate,
    current_user: User = Depends(get_admin_user)
):
    """Create a new user (admin only)"""
    db = ad.common.get_async_db()
    # Check total users limit
    total_users = await db.users.count_documents({})
    if total_users >= limits.MAX_TOTAL_USERS:
        raise HTTPException(
            status_code=403,
            detail="System limit reached: Maximum number of users exceeded"
        )

    # Check if email already exists
    if await db.users.find_one({"email": user.email}):
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    # Check if an organization exists with same name as the user email
    existing_org = await db.organizations.find_one({"name": user.email})
    if existing_org:
        raise HTTPException(
            status_code=400,
            detail=f"An organization with the same name as the user email ({user.email}) already exists"
        )
    
    # Hash password
    hashed_password = hashpw(user.password.encode(), gensalt(12))
    
    user_doc = {
        "email": user.email,
        "name": user.name,
        "password": hashed_password.decode(),
        "email_verified": True,
        "created_at": datetime.now(UTC),
        "has_seen_tour": False,
    }

    result = await db.users.insert_one(user_doc)
    stored = await db.users.find_one({"_id": result.inserted_id})
    logger.info(f"Created new user {user.email} with id {result.inserted_id}")
    
    # Create default individual organization for new user
    user_id = str(result.inserted_id)
    result = await db.organizations.insert_one({
        "name": user.email,
        "permission_groups": builtin_permission_groups_document(),
        "members": [build_member_entry(user_id, permission_group_ids=[BUILTIN_ADMIN])],
        "type": "individual",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    })

    org_id = str(result.inserted_id)
    logger.info(f"Created new organization {user.email} with id {org_id}")

    # Sync the organization (local and Stripe if configured)
    await sync_customer(db=db, org_id=org_id)
    
    return _user_document_to_response(stored)

@users_router.put("/v0/account/users/{user_id}", response_model=UserResponse, tags=["account/users"])
async def update_user(
    user_id: str,
    user: UserUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update a user's details (admin or self)"""
    db = ad.common.get_async_db()
    # Check if user has permission (admin or self)
    is_sys_admin = await is_system_admin(current_user.user_id)
    is_self = current_user.user_id == user_id
    
    if not (is_sys_admin or is_self):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update this user"
        )
    
    # For self-updates, only allow name changes
    update_data = {}
    if is_self and not is_sys_admin:
        if user.name is not None:
            update_data["name"] = user.name
        if user.password is not None:
            update_data["password"] = hashpw(user.password.encode(), gensalt(12)).decode()
        if user.has_seen_tour is not None:
            update_data["has_seen_tour"] = user.has_seen_tour
    else:
        payload = user.model_dump(exclude_none=True)
        sysadmin_change = payload.pop("is_sysadmin", None)
        update_data = payload
        if "password" in update_data:
            update_data["password"] = hashpw(update_data["password"].encode(), gensalt(12)).decode()

        mongo_update: dict = {}
        if update_data:
            mongo_update["$set"] = update_data
        if sysadmin_change is not None:
            target_user = await db.users.find_one({"_id": ObjectId(user_id)})
            if sysadmin_change:
                if not mongo_update.get("$set"):
                    mongo_update["$set"] = {}
                mongo_update["$set"]["system_role"] = SYSTEM_ROLE_SYSADMIN
            else:
                sysadmin_count = await db.users.count_documents({"system_role": SYSTEM_ROLE_SYSADMIN})
                if (
                    sysadmin_count == 1
                    and target_user
                    and user_document_is_sysadmin(target_user)
                ):
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot remove sysadmin from the last platform admin user",
                    )
                if not mongo_update.get("$unset"):
                    mongo_update["$unset"] = {}
                mongo_update["$unset"]["system_role"] = ""
            if not mongo_update.get("$unset"):
                mongo_update["$unset"] = {}
            mongo_update["$unset"]["role"] = ""

        if not mongo_update:
            raise HTTPException(
                status_code=400,
                detail="No valid update data provided",
            )

        result = await db.users.find_one_and_update(
            {"_id": ObjectId(user_id)},
            mongo_update,
            return_document=True,
        )
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        return _user_document_to_response(result)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No valid update data provided"
        )

    result = await db.users.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": update_data},
        return_document=True
    )
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    return _user_document_to_response(result)

@users_router.delete("/v0/account/users/{user_id}", tags=["account/users"])
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a user (admin or self)"""
    db = ad.common.get_async_db()

    # Check if user has permission (admin or self)
    is_sys_admin = await is_system_admin(current_user.user_id)
    is_self = current_user.user_id == user_id
    
    if not (is_sys_admin or is_self):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this user"
        )

    # Is the user an admin of any organization?
    orgs = await db.organizations.find({"members.user_id": user_id}).to_list(None)
    if orgs:
        for org in orgs:
            # Is this a single-user organization?
            members = org["members"]
            if len(members) == 1:
                logger.info(f"Deleting single-user organization {org['_id']}")
                # Delete the organization
                await db.organizations.delete_one({"_id": org["_id"]})
                await delete_payments_customer(db, org_id=org["_id"])
                continue
            
            # Is this the last admin of the organization?
            admin_count = 0
            is_org_admin = False
            for member in members:
                if member_has_admin_group(member):
                    admin_count += 1
                    if member["user_id"] == user_id:
                        is_org_admin = True
            if is_org_admin and admin_count == 1:
                raise HTTPException(
                    status_code=400,
                    detail="User is the last admin of an organization and cannot be deleted"
                )
            
            # Remove the user from the organization
            logger.info(f"Removing user {user_id} from organization {org['_id']}")
            await db.organizations.update_one(
                {"_id": org["_id"]},
                {"$pull": {"members": {"user_id": user_id}}}
            )

            # Update the payments customer (and Stripe if configured)
            await sync_customer(db=db, org_id=org["_id"])
    
    # Don't allow deleting the last admin user
    target_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target_user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    if user_document_is_sysadmin(target_user):
        sysadmin_count = await db.users.count_documents({"system_role": SYSTEM_ROLE_SYSADMIN})
        if sysadmin_count == 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last system admin user",
            )
    
    try:
        await users.delete_user(db, user_id)
        return {"message": "User and related data deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete user and related data"
        )
