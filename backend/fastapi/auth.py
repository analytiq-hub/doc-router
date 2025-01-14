from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from bson import ObjectId
from typing import Optional
import os
from datetime import datetime

import analytiq_data as ad
from globals import get_db, get_fastapi_secret
from schemas import User

# Initialize security
security = HTTPBearer()

# JWT settings
ALGORITHM = "HS256"

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> User:
    """Validate user from JWT token or API token"""
    token = credentials.credentials
    db = get_db()
    fastapi_secret = get_fastapi_secret()
    
    try:
        # First, try to validate as JWT
        payload = jwt.decode(token, fastapi_secret, algorithms=[ALGORITHM])
        userId: str = payload.get("userId")
        userName: str = payload.get("userName")
        email: str = payload.get("email")
        ad.log.debug(f"get_current_user(): userId: {userId}, userName: {userName}, email: {email}")
        if userName is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        # Validate that userId exists in database
        user = await db.users.find_one({"_id": ObjectId(userId)})
        if not user:
            raise HTTPException(status_code=401, detail="User not found in database")
            
        return User(user_id=userId,
                   user_name=userName,
                   token_type="jwt")
                   
    except JWTError:
        ad.log.debug(f"get_current_user(): JWT validation failed")
        # If JWT validation fails, check if it's an API token
        access_token_collection = db.access_tokens
        encrypted_token = ad.crypto.encrypt_token(token)
        stored_token = await access_token_collection.find_one({"token": encrypted_token})
        
        if stored_token:
            # Validate that user_id from stored token exists in database
            user = await db.users.find_one({"_id": ObjectId(stored_token["user_id"])})
            if not user:
                raise HTTPException(status_code=401, detail="User not found in database")
                
            return User(
                user_id=stored_token["user_id"],
                user_name=stored_token["name"],
                token_type="api"
            )
                
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

async def get_admin_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> User:
    """Validate user has admin role"""
    user = await get_current_user(credentials)
    db = get_db()
    
    # Check if user has admin role in database
    db_user = await db.users.find_one({"_id": ObjectId(user.user_id)})
    if not db_user or db_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return user