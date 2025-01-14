from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, UTC
import secrets

import analytiq_data as ad
from setup import get_async_db
from auth import get_current_user
from schemas import (
    AccessToken,
    CreateAccessTokenRequest,
    ListAccessTokensResponse,
    User
)

access_tokens_router = APIRouter(
    prefix="/access_tokens",
    tags=["access_tokens"]
)

@access_tokens_router.post("", response_model=AccessToken)
async def access_token_create(
    request: CreateAccessTokenRequest,
    current_user: User = Depends(get_current_user)
):
    """Create an API token"""
    db = get_async_db()
    
    ad.log.debug(f"Creating API token for user: {current_user} request: {request}")
    token = secrets.token_urlsafe(32)
    new_token = {
        "user_id": current_user.user_id,
        "name": request.name,
        "token": ad.crypto.encrypt_token(token),  # Store encrypted token
        "created_at": datetime.now(UTC),
        "lifetime": request.lifetime
    }
    result = await db.access_tokens.insert_one(new_token)

    # Return the new token with the id
    new_token["token"] = token  # Return plaintext token to user
    new_token["id"] = str(result.inserted_id)
    return new_token

@access_tokens_router.get("", response_model=ListAccessTokensResponse)
async def access_token_list(current_user: User = Depends(get_current_user)):
    """List API tokens"""
    db = get_async_db()
    
    cursor = db.access_tokens.find({"user_id": current_user.user_id})
    tokens = await cursor.to_list(length=None)
    ret = [
        {
            "id": str(token["_id"]),
            "user_id": token["user_id"],
            "name": token["name"],
            "token": token["token"],
            "created_at": token["created_at"],
            "lifetime": token["lifetime"]
        }
        for token in tokens
    ]
    ad.log.debug(f"list_access_tokens(): {ret}")
    return ListAccessTokensResponse(access_tokens=ret)

@access_tokens_router.delete("/{token_id}")
async def access_token_delete(
    token_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete an API token"""
    db = get_async_db()
    
    result = await db.access_tokens.delete_one({
        "_id": ObjectId(token_id),
        "user_id": current_user.user_id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token deleted successfully"} 