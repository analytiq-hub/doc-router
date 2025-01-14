from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from bson import ObjectId
from typing import Optional
import os
from datetime import datetime


import analytiq_data as ad
from setup import get_async_db
from schemas import User

# Initialize security
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> User:
    """Validate user from JWT token or API token"""
    token = credentials.credentials
    db = get_async_db()
    fastapi_secret = os.getenv("FASTAPI_SECRET")
    if not fastapi_secret:
        ad.log.error("FASTAPI_SECRET environment variable not set")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error"
        )
    
    algorithm = "HS256"
    
    try:
        # First, try to validate as JWT
        ad.log.debug(f"Attempting to validate JWT token")
        payload = jwt.decode(token, fastapi_secret, algorithms=[algorithm])
        userId: str = payload.get("userId")
        userName: str = payload.get("userName")
        email: str = payload.get("email")
        ad.log.debug(f"get_current_user(): userId: {userId}, userName: {userName}, email: {email}")
        
        if not userId or not userName:
            ad.log.error("Missing userId or userName in token payload")
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        # Validate that userId exists in database
        user = await db.users.find_one({"_id": ObjectId(userId)})
        if not user:
            ad.log.error(f"User {userId} not found in database")
            raise HTTPException(status_code=401, detail="User not found in database")
            
        ad.log.debug(f"Successfully validated JWT token for user {userName}")
        return User(user_id=userId,
                   user_name=userName,
                   token_type="jwt")
                   
    except JWTError as e:
        ad.log.debug(f"JWT validation failed: {str(e)}")
        # If JWT validation fails, check if it's an API token
        try:
            access_token_collection = db.access_tokens
            encrypted_token = ad.crypto.encrypt_token(token)
            stored_token = await access_token_collection.find_one({"token": encrypted_token})
            
            if stored_token:
                # Validate that user_id from stored token exists in database
                user = await db.users.find_one({"_id": ObjectId(stored_token["user_id"])})
                if not user:
                    ad.log.error(f"User {stored_token['user_id']} from API token not found in database")
                    raise HTTPException(status_code=401, detail="User not found in database")
                    
                ad.log.debug(f"Successfully validated API token for user {stored_token['name']}")
                return User(
                    user_id=stored_token["user_id"],
                    user_name=stored_token["name"],
                    token_type="api"
                )
        except Exception as e:
            ad.log.error(f"Error validating API token: {str(e)}")
            
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

async def get_admin_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> User:
    """Validate user has admin role"""
    user = await get_current_user(credentials)
    db = get_async_db()
    
    if not await is_sys_admin(db, user.user_id):
        ad.log.error(f"get_admin_user(): User {user.user_id} is not an admin")
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return user

async def is_org_admin(db, org_id: str, user_id: str) -> bool:
    """Check if user is an admin of the organization
    
    Args:
        db: Database connection
        org_id: Organization ID
        user_id: User ID to check
        
    Returns:
        bool: True if user is admin, False otherwise
    """
    org = await db.organizations.find_one({
        "_id": ObjectId(org_id),
        "members": {
            "$elemMatch": {
                "user_id": user_id,
                "role": "admin"
            }
        }
    })
    return org is not None

async def is_sys_admin(db, user_id: str) -> bool:
    """Check if user is a system admin
    
    Args:
        db: Database connection
        user_id: User ID to check
        
    Returns:
        bool: True if user is system admin, False otherwise
    """
    user = await db.users.find_one({
        "_id": ObjectId(user_id),
        "role": "admin"
    })
    return user is not None