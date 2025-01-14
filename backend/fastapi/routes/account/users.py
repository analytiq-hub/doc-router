from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, UTC
from bson import ObjectId
from bcrypt import hashpw, gensalt
from typing import Optional

import analytiq_data as ad
from setup import get_async_db
from auth import get_current_user, get_admin_user
from schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    ListUsersResponse,
    User
)

account_users_router = APIRouter(
    prefix="/account/users",
    tags=["account/users"]
)

@account_users_router.get("", response_model=ListUsersResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_admin_user)
):
    """List users (admin only)"""
    db = get_async_db()
    
    # Get total count
    total_count = await db.users.count_documents({})
    
    # Get paginated users
    cursor = db.users.find({}).sort("_id", -1).skip(skip).limit(limit)
    users = await cursor.to_list(None)
    
    # Convert users to response format
    user_responses = []
    for user in users:
        user_responses.append(UserResponse(
            id=str(user["_id"]),
            email=user["email"],
            name=user.get("name"),
            role=user.get("role", "user"),
            emailVerified=user.get("emailVerified"),
            createdAt=user["createdAt"],
            hasPassword=bool(user.get("password"))
        ))
    
    return ListUsersResponse(
        users=user_responses,
        total_count=total_count,
        skip=skip
    )

@account_users_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_admin_user)
):
    """Get user details (admin only)"""
    db = get_async_db()
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=str(user["_id"]),
        email=user["email"],
        name=user.get("name"),
        role=user.get("role", "user"),
        emailVerified=user.get("emailVerified"),
        createdAt=user["createdAt"],
        hasPassword=bool(user.get("password"))
    )

@account_users_router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: User = Depends(get_admin_user)
):
    """Update user details (admin only)"""
    db = get_async_db()
    
    # Prepare update data
    update_data = {}
    if user_update.name is not None:
        update_data["name"] = user_update.name
    if user_update.password is not None:
        hashed_password = hashpw(user_update.password.encode(), gensalt(12))
        update_data["password"] = hashed_password.decode()
    if user_update.role is not None:
        update_data["role"] = user_update.role
    if user_update.emailVerified is not None:
        update_data["emailVerified"] = user_update.emailVerified
    
    result = await db.users.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": update_data},
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=str(result["_id"]),
        email=result["email"],
        name=result.get("name"),
        role=result.get("role", "user"),
        emailVerified=result.get("emailVerified"),
        createdAt=result["createdAt"],
        hasPassword=bool(result.get("password"))
    )

@account_users_router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_admin_user)
):
    """Delete a user (admin only)"""
    db = get_async_db()
    
    # Cannot delete self
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account"
        )
    
    result = await db.users.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted successfully"} 