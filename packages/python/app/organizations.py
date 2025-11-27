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

from app.routes.orgs import OrganizationUpdate

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
