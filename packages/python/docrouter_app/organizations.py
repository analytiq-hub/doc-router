from datetime import datetime, UTC
from bson import ObjectId
from typing import List
import logging
import os
import sys

from fastapi import HTTPException

# Set up the path first, before other imports
cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{cwd}/..")

from docrouter_app.models import OrganizationUpdate

def validate_organization_type_upgrade(current_type: str, new_type: str) -> bool:
    """
    Validate if the organization type upgrade is allowed.
    
    Args:
        current_type: Current organization type
        new_type: Requested new organization type
    
    Returns:
        bool: True if upgrade is valid, False otherwise
    """
    valid_upgrades = {
        "individual": ["individual", "team", "enterprise"],
        "team": ["team", "enterprise"],
        "enterprise": ["enterprise"]
    }
    return new_type in valid_upgrades.get(current_type, [])

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
    logging.info(f"Updating organization {organization_id} to type {update.type}")

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
    
    logging.info(f"Updated organization {organization_id} to type {update.type}")