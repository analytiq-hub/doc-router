# token.py

# Standard library imports
import json
import secrets
import hmac
import hashlib
import logging
import os
from datetime import datetime, UTC
from typing import Optional

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from bson import ObjectId
from jose import jwt
from pydantic import BaseModel

# Local imports
import analytiq_data as ad
from app.auth import (
    get_current_user,
    get_admin_user,
    is_system_admin,
    is_organization_member,
    get_org_id_from_token
)
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

# Environment variables
NEXTAUTH_SECRET = os.getenv("NEXTAUTH_SECRET")
ALGORITHM = "HS256"

# Organization-level access tokens
@token_router.post("/v0/orgs/{organization_id}/access_tokens", response_model=AccessToken, tags=["access_tokens"])
async def create_org_token(
    organization_id: str,
    request: CreateAccessTokenRequest,
    current_user: User = Depends(get_current_user)
):
    """Create an organization-level API token"""
    # Verify organization membership
    is_sys_admin = await is_system_admin(current_user.user_id)
    is_org_member = await is_organization_member(organization_id, current_user.user_id)

    if not is_sys_admin and not is_org_member:
        raise HTTPException(status_code=403, detail="You are not authorized to create an organization-level API token")
    
    db = ad.common.get_async_db()
    
    # Generate a globally unique token
    max_attempts = 10
    for attempt in range(max_attempts):
        token = f"org_{secrets.token_urlsafe(32)}"
        encrypted_token = ad.crypto.encrypt_token(token)
        
        # Check if token already exists
        existing_token = await db.access_tokens.find_one({"token": encrypted_token})
        if not existing_token:
            break
    else:
        raise HTTPException(status_code=500, detail="Failed to generate unique token after multiple attempts")
    
    new_token = {
        "user_id": current_user.user_id,
        "organization_id": organization_id,
        "name": request.name,
        "token": encrypted_token,
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
    current_user: User = Depends(get_current_user)
):
    """List organization-level API tokens"""
    # Verify organization membership
    is_sys_admin = await is_system_admin(current_user.user_id)
    is_org_member = await is_organization_member(organization_id, current_user.user_id)

    if not is_sys_admin and not is_org_member:
        raise HTTPException(status_code=403, detail="You are not authorized to list organization-level API tokens")
    
    db = ad.common.get_async_db()
    cursor = db.access_tokens.find({
        "user_id": current_user.user_id,
        "organization_id": organization_id
    })
    tokens = await cursor.to_list(length=None)
    ret = []
    for token in tokens:
        # Decrypt token to get preview (first 10 chars) for display
        token_preview = None
        try:
            decrypted_token = ad.crypto.decrypt_token(token["token"])
            token_preview = decrypted_token[:10] if len(decrypted_token) >= 10 else ""
        except Exception as e:
            logger.warning(f"Failed to decrypt token for preview: {e}")
            token_preview = None
        
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
    current_user: User = Depends(get_current_user)
):
    """Delete an organization-level API token"""
    # Verify organization membership
    is_sys_admin = await is_system_admin(current_user.user_id)
    is_org_member = await is_organization_member(organization_id, current_user.user_id)

    if not is_sys_admin and not is_org_member:
        raise HTTPException(status_code=403, detail="You are not authorized to delete an organization-level API token")
    
    db = ad.common.get_async_db()
    result = await db.access_tokens.delete_one({
        "_id": ObjectId(token_id),
        "user_id": current_user.user_id,
        "organization_id": organization_id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token deleted successfully"}

# Authentication token creation
@token_router.post("/v0/account/auth/token", tags=["account/auth"])
async def create_auth_token(request: Request):
    """
    Create an authentication token.
    Requires HMAC signature in X-Request-Signature header for authentication.
    """
    # Verify request signature
    signature = request.headers.get("X-Request-Signature")
    if not signature:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Request-Signature header"
        )

    if not NEXTAUTH_SECRET:
        logger.error("NEXTAUTH_SECRET not configured")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error"
        )

    # Get raw request body for signature verification
    raw_body = await request.body()

    # Verify signature using HMAC-SHA256 on the raw body
    expected_signature = hmac.new(
        NEXTAUTH_SECRET.encode('utf-8'),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        logger.warning(f"Invalid signature for token request")
        raise HTTPException(
            status_code=401,
            detail="Invalid request signature"
        )

    # Parse request body after signature verification
    try:
        user_data = json.loads(raw_body)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {str(e)}"
        )

    logger.debug(f"create_auth_token(): user_data: {user_data}")

    # Signature is valid, create token
    token = jwt.encode(
        {
            "userId": user_data["id"],
            "userName": user_data["name"],
            "email": user_data["email"]
        },
        NEXTAUTH_SECRET,
        algorithm=ALGORITHM
    )

    logger.debug(f"create_auth_token(): {token}")
    return {"token": token}

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
        encrypted_token = ad.crypto.encrypt_token(token)
        
        # Check if token already exists
        existing_token = await db.access_tokens.find_one({"token": encrypted_token})
        if not existing_token:
            break
    else:
        raise HTTPException(status_code=500, detail="Failed to generate unique token after multiple attempts")
    
    new_token = {
        "user_id": current_user.user_id,
        "organization_id": None,  # Explicitly set to None for account-level tokens
        "name": request.name,
        "token": encrypted_token,
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
            decrypted_token = ad.crypto.decrypt_token(token["token"])
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
    Get the organization ID associated with an API token.
    
    Returns the organization ID for org-specific tokens, 
    or null for account-level tokens.
    """
    try:
        org_id = await get_org_id_from_token(token)
        return {"organization_id": org_id}
    except HTTPException as e:
        raise HTTPException(status_code=401, detail="Invalid token")
