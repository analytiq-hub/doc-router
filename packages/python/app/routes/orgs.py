# orgs.py

# Standard library imports
import logging
from datetime import datetime, UTC
from typing import List, Literal, Optional
from enum import Enum

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from pydantic import BaseModel

# Local imports
import analytiq_data as ad
from app import limits
from app.auth import (
    get_current_user,
    is_system_admin,
    is_organization_admin,
)
from app.models import User
from app.routes.payments import sync_customer, delete_payments_customer

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
orgs_router = APIRouter()

# Organization models
class OrganizationMember(BaseModel):
    user_id: str
    role: Literal['admin', 'user']

# Add this new type definition near the top with other Literal types
OrganizationType = Literal["individual", "team", "enterprise"]

class OrganizationCreate(BaseModel):
    name: str
    type: OrganizationType = "individual"

class OrganizationUpdate(BaseModel):
    name: str | None = None
    type: OrganizationType = "individual"
    members: List[OrganizationMember] | None = None

class Organization(BaseModel):
    id: str
    name: str
    members: List[OrganizationMember]
    type: OrganizationType = "individual"
    created_at: datetime
    updated_at: datetime

class ListOrganizationsResponse(BaseModel):
    organizations: List[Organization]
    total_count: int
    skip: int

# Add this to your OrganizationType documentation if you have it
class OrganizationType(str, Enum):
    """
    Organization type with upgrade restrictions:
    - individual can upgrade to team or enterprise
    - team can upgrade to enterprise
    - enterprise cannot be downgraded
    """
    INDIVIDUAL = "individual"
    TEAM = "team"
    ENTERPRISE = "enterprise"

# Organization endpoints
@orgs_router.get("/v0/account/organizations", response_model=ListOrganizationsResponse, tags=["account/organizations"])
async def list_organizations(
    user_id: str | None = Query(None, description="Filter organizations by user ID"),
    organization_id: str | None = Query(None, description="Get a specific organization by ID"),
    name_search: str | None = Query(None, description="Case-insensitive search on organization name"),
    member_search: str | None = Query(None, description="Case-insensitive search on member name or email"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """
    List organizations or get a specific organization.
    - If organization_id is provided, returns just that organization
    - If user_id is provided, returns organizations for that user
    - Otherwise returns all organizations (admin only)
    - user_id and organization_id are mutually exclusive
    """
    logger.debug(f"list_organizations(): user_id: {user_id} organization_id: {organization_id} current_user: {current_user}")
    db = ad.common.get_async_db()
    is_sys_admin = await is_system_admin(current_user.user_id)

    # user_id and organization_id are mutually exclusive
    if user_id and organization_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both user_id and organization_id"
        )

    # Handle single organization request
    if organization_id:
        try:
            organization = await db.organizations.find_one({"_id": ObjectId(organization_id)})
        except:
            raise HTTPException(status_code=404, detail="Organization not found")
            
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Check permissions
        is_org_admin = await is_organization_admin(organization_id, current_user.user_id)

        if not (is_sys_admin or is_org_admin):
            raise HTTPException(
                status_code=403,
                detail="Not authorized to view this organization"
            )

        return ListOrganizationsResponse(organizations=[
            Organization(**{
                **organization,
                "id": str(organization["_id"]),
                "type": organization["type"]
            })
        ], total_count=1, skip=0)

    # Handle user filter
    if user_id:
        if not is_sys_admin and user_id != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to view other users' organizations"
            )
        filter_user_id = user_id
    else:
        filter_user_id = None if is_sys_admin else current_user.user_id

    # Build base filters
    and_filters = []
    if filter_user_id:
        and_filters.append({"members.user_id": filter_user_id})

    # Apply organization name search
    if name_search:
        and_filters.append({"name": {"$regex": name_search, "$options": "i"}})

    # Apply member name/email search
    if member_search:
        # Find users matching by name or email
        user_cursor = db.users.find({
            "$or": [
                {"name": {"$regex": member_search, "$options": "i"}},
                {"email": {"$regex": member_search, "$options": "i"}},
            ]
        }, {"_id": 1})
        matching_users = await user_cursor.to_list(None)
        matching_user_ids = [str(u["_id"]) for u in matching_users]
        if matching_user_ids:
            and_filters.append({"members.user_id": {"$in": matching_user_ids}})
        else:
            # No users matched; return empty result fast
            return ListOrganizationsResponse(organizations=[], total_count=0, skip=skip)

    final_query = {"$and": and_filters} if and_filters else {}

    total_count = await db.organizations.count_documents(final_query)
    cursor = db.organizations.find(final_query).sort("_id", -1).skip(skip).limit(limit)
    organizations = await cursor.to_list(None)

    ret = ListOrganizationsResponse(organizations=[
        Organization(**{
            **org,
            "id": str(org["_id"]),
            "type": org["type"]
        }) for org in organizations
    ], total_count=total_count, skip=skip)
    return ret

@orgs_router.post("/v0/account/organizations", response_model=Organization, tags=["account/organizations"])
async def create_organization(
    organization: OrganizationCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new organization"""
    db = ad.common.get_async_db()

    # Check total organizations limit
    total_orgs = await db.organizations.count_documents({})
    if total_orgs >= limits.MAX_TOTAL_ORGANIZATIONS:
        raise HTTPException(
            status_code=403,
            detail="System limit reached: Maximum number of organizations exceeded"
        )

    # Check user's organization limit
    user_orgs = await db.organizations.count_documents({
        "members.user_id": current_user.user_id
    })
    if user_orgs >= limits.MAX_ORGANIZATIONS_PER_USER:
        raise HTTPException(
            status_code=403,
            detail=f"User limit reached: Cannot be member of more than {limits.MAX_ORGANIZATIONS_PER_USER} organizations"
        )

    # Check for existing organization with same name (case-insensitive)
    existing = await db.organizations.find_one({
        "name": {"$regex": f"^{organization.name}$", "$options": "i"}
    })
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"An organization named '{organization.name}' already exists"
        )

    # If creating enterprise organization, verify system admin
    if organization.type == "enterprise":
        if not await is_system_admin(current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="Only system administrators can create Enterprise organizations"
            )

    organization_doc = {
        "name": organization.name,
        "members": [{
            "user_id": current_user.user_id,
            "role": "admin"
        }],
        "type": organization.type or "team",  # Default to team if not specified
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    }
    
    result = await db.organizations.insert_one(organization_doc)
    org_id = str(result.inserted_id)

    # Create corresponding payments customer (and Stripe if configured)
    await sync_customer(db=db, org_id=org_id)

    return Organization(**{
        **organization_doc,
        "id": org_id
    })

@orgs_router.put("/v0/account/organizations/{organization_id}", response_model=Organization, tags=["account/organizations"])
async def update_organization(
    organization_id: str,
    organization_update: OrganizationUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update an organization (account admin or organization admin)"""
    logger.info(f"Updating organization {organization_id} with {organization_update}")
    db = ad.common.get_async_db()

    organization = await db.organizations.find_one({"_id": ObjectId(organization_id)})
    if not organization:
        logger.error(f"Organization not found: {organization_id}")
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if user has permission (account admin or organization admin)
    is_sys_admin = await is_system_admin(current_user.user_id)
    is_org_admin = await is_organization_admin(organization_id, current_user.user_id)
    
    if not (is_sys_admin or is_org_admin):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update this organization"
        )

    # Is the type changing?
    if organization_update.type is not None and organization_update.type != organization["type"]:
        logger.info(f"Updating organization type from {organization['type']} to {organization_update.type}")
        await update_organization_type(
            db=db,
            organization_id=organization_id,
            update=organization_update,
            current_user_id=current_user.user_id
        )
        # Re-fetch organization after type update to get latest state
        organization = await db.organizations.find_one({"_id": ObjectId(organization_id)})
        if not organization:
            logger.error(f"Organization not found after type update: {organization_id}")
            raise HTTPException(status_code=404, detail="Organization not found")

    update_data = {}
    if organization_update.name is not None:
        update_data["name"] = organization_update.name
    
    if organization_update.members is not None:
        # Ensure at least one admin remains
        if not any(m.role == "admin" for m in organization_update.members):
            logger.error(f"Organization must have at least one admin: {organization_update.members}")
            raise HTTPException(
                status_code=400,
                detail="Organization must have at least one admin"
            )
        update_data["members"] = [m.dict() for m in organization_update.members]

    if update_data:
        update_data["updated_at"] = datetime.now(UTC)
        # Use find_one_and_update instead of update_one to get the updated document atomically
        updated_organization = await db.organizations.find_one_and_update(
            {"_id": ObjectId(organization_id)},
            {"$set": update_data},
            return_document=True  # Return the updated document
        )
        
        if not updated_organization:
            logger.error(f"Organization not found after update: {organization_id}")
            raise HTTPException(status_code=404, detail="Organization not found")
    else:
        # If no updates were needed, just return the current organization
        updated_organization = organization

    # Update the payments customer (and Stripe if configured)
    await sync_customer(db=db, org_id=organization_id)

    return Organization(**{
        "id": str(updated_organization["_id"]),
        "name": updated_organization["name"],
        "members": updated_organization["members"],
        "type": updated_organization["type"],
        "created_at": updated_organization["created_at"],
        "updated_at": updated_organization["updated_at"]
    })

@orgs_router.delete("/v0/account/organizations/{organization_id}", tags=["account/organizations"])
async def delete_organization(
    organization_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete an organization (account admin or organization admin)"""
    # Get organization and verify it exists
    db = ad.common.get_async_db()
    organization = await db.organizations.find_one({"_id": ObjectId(organization_id)})
    if not organization:
        raise HTTPException(404, "Organization not found")
    
    # Check if user has permission (account admin or organization admin)
    is_sys_admin = await is_system_admin(current_user.user_id)
    is_org_admin = await is_organization_admin(organization_id, current_user.user_id)
    
    if not (is_sys_admin or is_org_admin):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this organization"
        )

    # Delete the payments customer
    await delete_payments_customer(db=db, org_id=organization_id)
        
    await db.organizations.delete_one({"_id": ObjectId(organization_id)})
    return {"status": "success"}

# Helper function moved from organizations.py to avoid circular imports
async def update_organization_type(
    db, 
    organization_id: str, 
    update: OrganizationUpdate,
    current_user_id: str = None
) -> None:
    """
    Update an organization's type and handle member management.
    
    Args:
        db: MongoDB database instance
        organization_id: ID of the organization to update
        update: OrganizationUpdate model containing new type and optional members
        current_user_id: ID of the current user making the request
    """
    logger.info(f"Updating organization {organization_id} to type {update.type}")

    # Get the organization
    organization = await db.organizations.find_one({"_id": ObjectId(organization_id)})
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    if update.type is None:
        raise HTTPException(status_code=400, detail="New organization type is required")

    # Validate organization type upgrade
    current_type = organization["type"]
    if not validate_organization_type_upgrade(current_type, update.type):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid organization type upgrade. Cannot change from {current_type} to {update.type}"
        )

    # Check if user is trying to upgrade to Enterprise without system admin privileges
    if (current_type in ['individual', 'team'] and update.type == 'enterprise' and current_user_id):
        # Check if current user is a system admin
        user = await db.users.find_one({"_id": ObjectId(current_user_id)})
        if not user or user.get("role") != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only system administrators can upgrade organizations to Enterprise"
            )

    # Find the first admin in the current organization
    first_admin = next((m for m in organization["members"] if m["role"] == "admin"), None)
    if not first_admin:
        raise HTTPException(status_code=400, detail="Organization must have at least one admin")

    update_data = {}

    # Validate parameters based on new type
    if update.type in ["team", "enterprise"]:
        update_data["type"] = update.type
        if update.members:
            if not any(m.role == "admin" for m in update.members):
                raise HTTPException(status_code=400, detail="Organization must have at least one admin")
            update_data["members"] = [m.dict() for m in update.members]

    # Validate individual organization member count
    if update.type == "individual":
        if update.members:
            if len(update.members) > 1:
                raise HTTPException(
                    status_code=400, 
                    detail="Individual organizations cannot have multiple members"
                )
            if not any(m.role == "admin" for m in update.members):
                raise HTTPException(status_code=400, detail="Organization must have at least one admin")
            update_data["members"] = [m.dict() for m in update.members]

    # Update the organization
    update_data["updated_at"] = datetime.now(UTC)
    await db.organizations.update_one(
        {"_id": ObjectId(organization_id)},
        {"$set": update_data}
    )
    
    logger.info(f"Updated organization {organization_id} to type {update.type}")

def validate_organization_type_upgrade(current_type: str, new_type: str) -> bool:
    """
    Validate if the organization type upgrade is allowed.
    
    Args:
        current_type: Current organization type
        new_type: Desired new organization type
        
    Returns:
        bool: True if upgrade is allowed, False otherwise
    """
    valid_upgrades = {
        "individual": ["team", "enterprise"],
        "team": ["enterprise"],
        "enterprise": ["enterprise"]
    }
    return new_type in valid_upgrades.get(current_type, [])
