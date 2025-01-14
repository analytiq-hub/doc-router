from fastapi import APIRouter, HTTPException, Depends, Query, Body
from datetime import datetime, UTC
from bson import ObjectId
from typing import Optional

import analytiq_data as ad
from setup import get_async_db
from auth import get_current_user
from schemas import (
    Organization,
    OrganizationCreate,
    OrganizationUpdate,
    ListOrganizationsResponse,
    User
)

account_organizations_router = APIRouter(
    prefix="/account/organizations",
    tags=["account/organizations"]
)

@account_organizations_router.post("", response_model=Organization)
async def create_organization(
    org: OrganizationCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new organization"""
    db = get_async_db()
    
    # Check if organization with this name already exists
    existing_org = await db.organizations.find_one({"name": org.name})
    if existing_org:
        raise HTTPException(
            status_code=400,
            detail=f"Organization with name '{org.name}' already exists"
        )
    
    # Create organization document
    org_dict = {
        "name": org.name,
        "type": org.type,
        "members": [{
            "user_id": current_user.user_id,
            "role": "admin"  # Creator is always admin
        }],
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    }
    
    result = await db.organizations.insert_one(org_dict)
    org_dict["id"] = str(result.inserted_id)
    
    return Organization(**org_dict)

@account_organizations_router.get("", response_model=ListOrganizationsResponse)
async def list_organizations(
    current_user: User = Depends(get_current_user)
):
    """List organizations the user is a member of"""
    db = get_async_db()
    
    cursor = db.organizations.find({
        "members.user_id": current_user.user_id
    })
    orgs = await cursor.to_list(None)
    
    # Convert _id to id in each organization
    for org in orgs:
        org["id"] = str(org.pop("_id"))
    
    return ListOrganizationsResponse(organizations=orgs)

@account_organizations_router.get("/{org_id}", response_model=Organization)
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get organization details"""
    db = get_async_db()
    
    org = await db.organizations.find_one({
        "_id": ObjectId(org_id),
        "members.user_id": current_user.user_id
    })
    
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    org["id"] = str(org.pop("_id"))
    return Organization(**org)

@account_organizations_router.put("/{org_id}", response_model=Organization)
async def update_organization(
    org_id: str,
    org_update: OrganizationUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update organization details"""
    db = get_async_db()
    
    # Check if user is admin of the organization
    org = await db.organizations.find_one({
        "_id": ObjectId(org_id),
        "members": {
            "$elemMatch": {
                "user_id": current_user.user_id,
                "role": "admin"
            }
        }
    })
    
    if not org:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update this organization"
        )
    
    # Prepare update data
    update_data = {
        "updated_at": datetime.now(UTC)
    }
    if org_update.name is not None:
        update_data["name"] = org_update.name
    if org_update.type is not None:
        update_data["type"] = org_update.type
    if org_update.members is not None:
        update_data["members"] = [member.dict() for member in org_update.members]
    
    result = await db.organizations.find_one_and_update(
        {"_id": ObjectId(org_id)},
        {"$set": update_data},
        return_document=True
    )
    
    result["id"] = str(result.pop("_id"))
    return Organization(**result)

@account_organizations_router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete an organization"""
    db = get_async_db()
    
    # Check if user is admin of the organization
    org = await db.organizations.find_one({
        "_id": ObjectId(org_id),
        "members": {
            "$elemMatch": {
                "user_id": current_user.user_id,
                "role": "admin"
            }
        }
    })
    
    if not org:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this organization"
        )
    
    # Cannot delete individual organizations
    if org["type"] == "individual":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete individual organizations"
        )
    
    result = await db.organizations.delete_one({"_id": ObjectId(org_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return {"message": "Organization deleted successfully"} 