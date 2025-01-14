from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, UTC
from bson import ObjectId

import analytiq_data as ad
from setup import get_async_db
from auth import get_admin_user
from schemas import (
    LLMToken,
    CreateLLMTokenRequest,
    ListLLMTokensResponse,
    User
)

account_llm_tokens_router = APIRouter(
    prefix="/account/llm_tokens",
    tags=["account/llm_tokens"]
)

@account_llm_tokens_router.post("", response_model=LLMToken)
async def llm_token_create(
    request: CreateLLMTokenRequest,
    current_user: User = Depends(get_admin_user)
):
    """Create or update an LLM token (admin only)"""
    db = get_async_db()
    ad.log.debug(f"Creating/Updating LLM token for user: {current_user} request: {request}")
    
    # Check if a token for this vendor already exists
    existing_token = await db.llm_tokens.find_one({
        "user_id": current_user.user_id,
        "llm_vendor": request.llm_vendor
    })

    new_token = {
        "user_id": current_user.user_id,
        "llm_vendor": request.llm_vendor,
        "token": ad.crypto.encrypt_token(request.token),
        "created_at": datetime.now(UTC),
    }

    if existing_token:
        # Update the existing token
        result = await db.llm_tokens.replace_one(
            {"_id": existing_token["_id"]},
            new_token
        )
        new_token["id"] = str(existing_token["_id"])
        ad.log.debug(f"Updated existing LLM token for {request.llm_vendor}")
    else:
        # Insert a new token
        result = await db.llm_tokens.insert_one(new_token)
        new_token["id"] = str(result.inserted_id)
        new_token["token"] = ad.crypto.decrypt_token(new_token["token"])
        ad.log.debug(f"Created new LLM token for {request.llm_vendor}")

    return new_token

@account_llm_tokens_router.get("", response_model=ListLLMTokensResponse)
async def llm_token_list(current_user: User = Depends(get_admin_user)):
    """List LLM tokens (admin only)"""
    db = get_async_db()
    
    cursor = db.llm_tokens.find({"user_id": current_user.user_id})
    tokens = await cursor.to_list(length=None)
    ret = [
        {
            "id": str(token["_id"]),
            "user_id": token["user_id"],
            "llm_vendor": token["llm_vendor"],
            "token": ad.crypto.decrypt_token(token["token"]),
            "created_at": token["created_at"]
        }
        for token in tokens
    ]
    ad.log.debug(f"list_llm_tokens(): {ret}")
    return ListLLMTokensResponse(llm_tokens=ret)

@account_llm_tokens_router.delete("/{token_id}")
async def llm_token_delete(
    token_id: str,
    current_user: User = Depends(get_admin_user)
):
    """Delete an LLM token (admin only)"""
    db = get_async_db()
    
    result = await db.llm_tokens.delete_one({
        "_id": ObjectId(token_id),
        "user_id": current_user.user_id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token deleted successfully"} 