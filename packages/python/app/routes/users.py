# users.py

# Standard library imports
import logging
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
from app.auth import (
    get_current_user,
    get_admin_user,
    is_system_admin,
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
    role: str | None = None  # Replace isAdmin with role
    email_verified: bool | None = None
    has_seen_tour: bool | None = None

class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    email_verified: bool | None
    created_at: datetime
    has_password: bool
    has_seen_tour: bool | None = None

class ListUsersResponse(BaseModel):
    users: List[UserResponse]
    total_count: int
    skip: int

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
            # Check if user is an org admin for any org the target user is in
            user_orgs = await db.organizations.find({
                "members.user_id": user_id
            }).to_list(None)
            
            is_org_admin = any(
                any(m["user_id"] == current_user.user_id and m["role"] == "admin" 
                    for m in org["members"])
                for org in user_orgs
            )
            
            if not is_org_admin:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to view this user"
                )
                
        ret = ListUsersResponse(
            users=[UserResponse(
                id=str(user["_id"]),
                email=user["email"],
                name=user.get("name"),
                role=user.get("role", "user"),
                email_verified=user.get("email_verified"),
                created_at=user.get("created_at", datetime.now(UTC)),
                has_password=bool(user.get("password"))
            )],
            total_count=1,
            skip=0
        )
        return ret

    # Handle organization filter
    if organization_id:
        org = await db.organizations.find_one({"_id": ObjectId(organization_id)})
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
            
        is_org_admin = any(
            m["user_id"] == current_user.user_id and m["role"] == "admin" 
            for m in org["members"]
        )
        
        if not (is_sys_admin or is_org_admin):
            raise HTTPException(
                status_code=403, 
                detail="Not authorized to view organization users"
            )
            
        member_ids = [m["user_id"] for m in org["members"]]
        and_filters.append({"_id": {"$in": [ObjectId(uid) for uid in member_ids]}})
    elif not is_sys_admin:
        # List all users in organizations the current user is an admin of
        orgs = await db.organizations.find({
            "members.user_id": current_user.user_id,
            "members.role": "admin"
        }).to_list(None)
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
        or_filter = {
            "$or": [
                {"name": {"$regex": search_name, "$options": "i"}},
                {"email": {"$regex": search_name, "$options": "i"}},
            ]
        }
        and_filters.append(or_filter)

    final_query = {"$and": and_filters} if and_filters else {}

    total_count = await db.users.count_documents(final_query)
    users = await db.users.find(final_query).skip(skip).limit(limit).to_list(None)

    ret = ListUsersResponse(
        users=[
            UserResponse(
                id=str(user["_id"]),
                email=user["email"],
                name=user.get("name"),
                role=user.get("role", "user"),
                email_verified=user.get("email_verified"),
                created_at=user.get("created_at", datetime.now(UTC)),
                has_password=bool(user.get("password"))
            )
            for user in users
        ],
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
    
    # Create user document with default role
    user_doc = {
        "email": user.email,
        "name": user.name,
        "password": hashed_password.decode(),
        "role": "user",  # Always set default role as user
        "email_verified": True,
        "created_at": datetime.now(UTC),
        "has_seen_tour": False
    }
    
    result = await db.users.insert_one(user_doc)
    user_doc["id"] = str(result.inserted_id)
    user_doc["has_password"] = True

    logger.info(f"Created new user {user.email} with id {user_doc['id']}")
    
    # Create default individual organization for new user
    result = await db.organizations.insert_one({
        "name": user.email,
        "members": [{
            "user_id": str(result.inserted_id),
            "role": "admin"
        }],
        "type": "individual",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    })

    org_id = str(result.inserted_id)
    logger.info(f"Created new organization {user.email} with id {org_id}")

    # Sync the organization (local and Stripe if configured)
    await sync_customer(db=db, org_id=org_id)
    
    return UserResponse(**user_doc)

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
        # Admin can update all fields
        update_data = {
            k: v for k, v in user.model_dump().items() 
            if v is not None
        }
        
        # If password is included, hash it
        if "password" in update_data:
            update_data["password"] = hashpw(update_data["password"].encode(), gensalt(12)).decode()
        
        # Don't allow updating the last admin user to non-admin
        if user.role == "user":
            admin_count = await db.users.count_documents({"role": "admin"})
            target_user = await db.users.find_one({"_id": ObjectId(user_id)})
            if admin_count == 1 and target_user and target_user.get("role") == "admin":
                raise HTTPException(
                    status_code=400,
                    detail="Cannot remove admin role from the last admin user"
                )
    
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
    
    return UserResponse(
        id=str(result["_id"]),
        email=result["email"],
        name=result.get("name"),
        role=result.get("role", "user"),
        email_verified=result.get("email_verified"),
        created_at=result.get("created_at", datetime.now(UTC)),
        has_password=bool(result.get("password"))
    )

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
                if member["role"] == "admin":
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
    
    if target_user.get("role") == "admin":
        admin_count = await db.users.count_documents({"role": "admin"})
        if admin_count == 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last system admin user"
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
