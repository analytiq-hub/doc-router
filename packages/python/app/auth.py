# Standard library imports
import os
import logging
from typing import Optional, Tuple
from contextlib import asynccontextmanager
from bson import ObjectId

# Third-party imports
from fastapi import (
    FastAPI, HTTPException, Depends, Security, Request
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from dotenv import load_dotenv

# Local imports
import analytiq_data as ad

from app.models import User

# Set up the environment variables. This reads the .env file.
ad.common.setup()

# Environment variables
ENV = os.getenv("ENV", "dev")
NEXTAUTH_URL = os.getenv("NEXTAUTH_URL")
FASTAPI_ROOT_PATH = os.getenv("FASTAPI_ROOT_PATH", "/")
MONGODB_URI = os.getenv("MONGODB_URI")

logger = logging.getLogger(__name__)

# JWT settings
NEXTAUTH_SECRET = os.getenv("NEXTAUTH_SECRET")
ALGORITHM = "HS256"

# Security scheme for JWT authentication
security = HTTPBearer()

def get_api_context(path: str) -> tuple[str, Optional[str]]:
    """
    Parse the API path to determine context (account vs org) and org_id if present.
    Returns (context_type, organization_id)
    """
    parts = path.split('/')
    if len(parts) > 2 and parts[2] == "account":
        return "account", None
    elif len(parts) > 2 and parts[2] == "orgs":
        return "organization", parts[3]
    return "unknown", None

def extract_org_id_from_path(path: str) -> Optional[str]:
    """
    Extract organization ID from the path.
    """
    parts = path.split('/')
    if len(parts) > 2 and parts[2] == "orgs":
        return parts[3]
    return None

async def get_session_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Get the current user from JWT session token only (no API tokens allowed).
    Used for endpoints that should only be accessible via browser sessions.
    """
    db = ad.common.get_async_db()
    token = credentials.credentials

    try:
        # Only validate as JWT (no API token fallback)
        payload = jwt.decode(token, NEXTAUTH_SECRET, algorithms=[ALGORITHM])
        userId: str = payload.get("userId")
        userName: str = payload.get("userName")
        email: str = payload.get("email")

        if userName is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials: missing userName")

        # Validate that userId exists in database
        user = await db.users.find_one({"_id": ObjectId(userId)})
        if not user:
            raise HTTPException(status_code=401, detail=f"User id '{userId}' not found in database")

        return User(
            user_id=userId,
            user_name=userName,
            token_type="jwt"
        )

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid session token. Only browser sessions are allowed for this endpoint."
        )

# Modify get_current_user to validate based on context
async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security), request: Request = None):
    """
    Validate user based on JWT or API token, considering the API context.
    Account APIs only accept account-level tokens.
    Organization APIs only accept org-specific tokens for that organization.
    """
    db = ad.common.get_async_db()
    token = credentials.credentials
    
    # Get API context
    context_type, org_id = get_api_context(request.url.path)
    
    try:
        # First, try to validate as JWT using the session user function
        return await get_session_user(credentials)
                   
    except HTTPException:
        # If JWT validation fails, check if it's an API token
        encrypted_token = ad.crypto.encrypt_token(token)
        
        # Build query based on context
        token_query = {"token": encrypted_token}
        
        if context_type == "account":
            # For account APIs, only accept account-level tokens
            token_query["organization_id"] = None
        elif context_type == "organization" and org_id:
            # For org APIs, only accept tokens for that specific org
            token_query["organization_id"] = org_id
        else:
            raise HTTPException(status_code=401, detail=f"Invalid API context: '{context_type}'")
            
        stored_token = await db.access_tokens.find_one(token_query)
        
        if stored_token:
            # Validate that user_id from stored token exists in database
            user = await db.users.find_one({"_id": ObjectId(stored_token["user_id"])})
            if not user:
                raise HTTPException(status_code=401, detail="User not found in database")

            # Extract organization from URL path
            path = request.url.path if request else ""
            org_id = extract_org_id_from_path(path)  # You'd need to implement this
            
            # Check if token's organization matches URL organization
            if org_id and stored_token.get("organization_id") != org_id:
                raise HTTPException(
                    status_code=403,
                    detail="Token is not valid for this organization"
                )
                
            return User(
                user_id=stored_token["user_id"],
                user_name=stored_token["name"],
                token_type="api"
            )
                
        raise HTTPException(status_code=401, detail="Invalid authentication credentials: invalid token")

# Add this helper function to check admin status
async def get_admin_user(credentials: HTTPAuthorizationCredentials = Security(security), request: Request = None):
    user = await get_current_user(credentials, request)

    if not await is_system_admin(user.user_id):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return user

async def is_system_admin(user_id: str):
    """
    Check if a user is an admin

    Args:
        user_id: The ID of the user to check

    Returns:
        True if the user is an admin, False otherwise
    """
    db = ad.common.get_async_db()
    db_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not db_user or db_user.get("role") != "admin":
        return False
    return True

async def is_organization_admin(org_id: str, user_id: str):
    """
    Check if a user is an org admin

    Args:
        org_id: The ID of the organization to check
        user_id: The ID of the user to check

    Returns:
        True if the user is an org admin, False otherwise
    """
    db = ad.common.get_async_db()
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        logger.info(f"Org not found for org_id: {org_id}")
        return False

    for member in org.get("members", []):
        if member.get("user_id") == user_id and member.get("role") == "admin":
            return True

    return False

async def is_organization_member(org_id: str, user_id: str):
    """
    Check if a user is a member of an organization
    """
    db = ad.common.get_async_db()
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        logger.info(f"Org not found for org_id: {org_id}")
        return False
    
    for member in org.get("members", []):
        if member.get("user_id") == user_id:
            return True

    return False

async def get_org_user(
    organization_id: str,
    current_user: User = Depends(get_current_user)
):
    is_member = await is_organization_member(organization_id, current_user.user_id)
    if not is_member:
        raise HTTPException(status_code=403, detail="You are not a member of this organization")
    return current_user

async def get_org_admin_user(
    organization_id: str,
    current_user: User = Depends(get_current_user)
):
    is_admin = await is_organization_admin(organization_id, current_user.user_id)
    if is_admin:
        return current_user
    raise HTTPException(status_code=403, detail="You are not an admin of this organization")

async def get_admin_or_org_user(
    organization_id: str,
    current_user: User = Depends(get_current_user)
):
    is_admin = await is_system_admin(current_user.user_id)
    if is_admin:
        return current_user
    is_member = await is_organization_member(organization_id, current_user.user_id)
    if not is_member:
        raise HTTPException(status_code=403, detail="You are not a member of this organization")

    return current_user

async def get_org_id_from_token(token: str) -> Optional[str]:
    """
    Resolve an API token to its organization ID.
    
    Args:
        token: The API token to resolve
        
    Returns:
        The organization ID if the token is valid and org-specific, 
        None if account-level token, or raises HTTPException if invalid
        
    Raises:
        HTTPException: If the token is invalid or not found
    """
    db = ad.common.get_async_db()
    encrypted_token = ad.crypto.encrypt_token(token)
    
    stored_token = await db.access_tokens.find_one({"token": encrypted_token})
    if not stored_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return stored_token.get("organization_id")