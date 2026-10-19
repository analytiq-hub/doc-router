# token.py

# Standard library imports
import secrets
import logging
from datetime import datetime, UTC
from typing import Optional

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from pydantic import BaseModel

# Local imports
import analytiq_data as ad
from app.auth import (
    get_current_user,
    get_admin_user,
    get_org_id_from_token,
)
from app.org_auth import get_org_user
from app.models import User

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
token_router = APIRouter()

class AccessToken(BaseModel):
    id: str
    user_id: str
    organization_id: Optional[str] = None
    name: str
    token: str
    created_at: datetime
    lifetime: int

class ListAccessTokensResponse(BaseModel):
    access_tokens: list[AccessToken]

class CreateAccessTokenRequest(BaseModel):
    name: str
    lifetime: int

# Organization-level access tokens
@token_router.post("/v0/orgs/{organization_id}/access_tokens", response_model=AccessToken, tags=["access_tokens"])
async def create_org_token(
    organization_id: str,
    request: CreateAccessTokenRequest,
    current_user: User = Depends(get_org_user),
):
    """Create an organization-level API token"""
    db = ad.common.get_async_db()
    
    # Generate a globally unique token
    max_attempts = 10
    for attempt in range(max_attempts):
        token = f"org_{secrets.token_urlsafe(32)}"
        fingerprint = ad.crypto.fingerprint_secret(token)

        # Check if token already exists (lookup by deterministic fingerprint;
        # stored ciphertext uses a random IV).
        existing_token = await db.access_tokens.find_one({"fingerprint": fingerprint})
        if not existing_token:
            break
    else:
        raise HTTPException(status_code=500, detail="Failed to generate unique token after multiple attempts")

    new_token = {
        "user_id": current_user.user_id,
        "organization_id": organization_id,
        "name": request.name,
        "token": ad.crypto.encrypt_secret(token),
        "fingerprint": fingerprint,
        "created_at": datetime.now(UTC),
        "lifetime": request.lifetime
    }
    try:
        result = await db.access_tokens.insert_one(new_token)
    except Exception as e:
        # Handle potential duplicate key error from database unique constraint
        if "duplicate key" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=500, detail="Token collision detected. Please try again.")
        raise

    new_token["token"] = token  # Return plaintext token to user
    new_token["id"] = str(result.inserted_id)
    return new_token

@token_router.get("/v0/orgs/{organization_id}/access_tokens", response_model=ListAccessTokensResponse, tags=["access_tokens"])
async def list_org_tokens(
    organization_id: str,
    current_user: User = Depends(get_org_user),
):
    """List organization-level API tokens"""
    db = ad.common.get_async_db()
    cursor = db.access_tokens.find({
        "user_id": current_user.user_id,
        "organization_id": organization_id
    })
    tokens = await cursor.to_list(length=None)
    ret = []
    for token in tokens:
        # Decrypt token to get preview (first 10 chars) for display
        token_preview = ""
        try:
            decrypted_token = ad.crypto.decrypt_secret(token["token"])
            token_preview = decrypted_token[:10] if len(decrypted_token) >= 10 else ""
        except Exception as e:
            logger.warning(f"Failed to decrypt token for preview: {e}")
            token_preview = ""
        
        ret.append({
            "id": str(token["_id"]),
            "user_id": token["user_id"],
            "organization_id": token["organization_id"],
            "name": token["name"],
            "token": token_preview,  # Return preview in token field
            "created_at": token["created_at"],
            "lifetime": token["lifetime"]
        })
    return ListAccessTokensResponse(access_tokens=ret)

@token_router.delete("/v0/orgs/{organization_id}/access_tokens/{token_id}", tags=["access_tokens"])
async def delete_org_token(
    organization_id: str,
    token_id: str,
    current_user: User = Depends(get_org_user),
):
    """Delete an organization-level API token"""
    db = ad.common.get_async_db()
    result = await db.access_tokens.delete_one({
        "_id": ObjectId(token_id),
        "user_id": current_user.user_id,
        "organization_id": organization_id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token deleted successfully"}

# Account-level access tokens
@token_router.post("/v0/account/access_tokens", response_model=AccessToken, tags=["account/access_tokens"])
async def create_account_token(
    request: CreateAccessTokenRequest,
    current_user: User = Depends(get_current_user)
):
    """Create an account-level API token"""
    logger.debug(f"Creating account token for user: {current_user} request: {request}")
    db = ad.common.get_async_db()

    # Generate a globally unique token
    max_attempts = 10
    for attempt in range(max_attempts):
        token = f"acc_{secrets.token_urlsafe(32)}"
        fingerprint = ad.crypto.fingerprint_secret(token)

        # Check if token already exists (lookup by deterministic fingerprint;
        # stored ciphertext uses a random IV).
        existing_token = await db.access_tokens.find_one({"fingerprint": fingerprint})
        if not existing_token:
            break
    else:
        raise HTTPException(status_code=500, detail="Failed to generate unique token after multiple attempts")

    new_token = {
        "user_id": current_user.user_id,
        "organization_id": None,  # Explicitly set to None for account-level tokens
        "name": request.name,
        "token": ad.crypto.encrypt_secret(token),
        "fingerprint": fingerprint,
        "created_at": datetime.now(UTC),
        "lifetime": request.lifetime
    }
    try:
        result = await db.access_tokens.insert_one(new_token)
    except Exception as e:
        # Handle potential duplicate key error from database unique constraint
        if "duplicate key" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=500, detail="Token collision detected. Please try again.")
        raise

    new_token["token"] = token  # Return plaintext token to user
    new_token["id"] = str(result.inserted_id)
    return new_token

@token_router.get("/v0/account/access_tokens", response_model=ListAccessTokensResponse, tags=["account/access_tokens"])
async def list_account_tokens(
    current_user: User = Depends(get_current_user)
):
    """List account-level API tokens"""
    db = ad.common.get_async_db()
    
    cursor = db.access_tokens.find({
        "user_id": current_user.user_id,
        "organization_id": None  # Only get account-level tokens
    })
    tokens = await cursor.to_list(length=None)
    ret = []
    for token in tokens:
        # Decrypt token to get preview (first 10 chars)
        token_preview = ""
        try:
            decrypted_token = ad.crypto.decrypt_secret(token["token"])
            token_preview = decrypted_token[:10] if len(decrypted_token) >= 10 else ""
        except Exception as e:
            logger.warning(f"Failed to decrypt token for preview: {e}")
            token_preview = ""
        
        ret.append({
            "id": str(token["_id"]),
            "user_id": token["user_id"],
            "organization_id": None,
            "name": token["name"],
            "token": token_preview,  # Return preview in token field
            "created_at": token["created_at"],
            "lifetime": token["lifetime"]
        })
    return ListAccessTokensResponse(access_tokens=ret)

@token_router.delete("/v0/account/access_tokens/{token_id}", tags=["account/access_tokens"])
async def delete_account_token(
    token_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete an account-level API token"""
    db = ad.common.get_async_db()
    
    result = await db.access_tokens.delete_one({
        "_id": ObjectId(token_id),
        "user_id": current_user.user_id,
        "organization_id": None  # Only delete account-level tokens
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token deleted successfully"}

@token_router.get("/v0/account/token/organization", tags=["account/auth"])
async def get_organization_from_token(
    token: str = Query(..., description="The API token to resolve to organization ID")
):
    """
    Get the organization information associated with an API token.

    Returns the organization ID, name, and type for org-specific tokens,
    or null values for account-level tokens.
    """
    try:
        org_id = await get_org_id_from_token(token)

        # If it's an account-level token (no org_id), return null values
        if org_id is None:
            return {
                "organization_id": None,
                "organization_name": None,
                "organization_type": None
            }

        # Fetch organization details
        db = ad.common.get_async_db()
        org = await db.organizations.find_one({"_id": ObjectId(org_id)})

        if not org:
            # Token references an org that no longer exists
            return {
                "organization_id": org_id,
                "organization_name": None,
                "organization_type": None
            }

        return {
            "organization_id": org_id,
            "organization_name": org.get("name"),
            "organization_type": org.get("type")
        }
    except HTTPException as e:
        raise HTTPException(status_code=401, detail="Invalid token")
