# aws.py

# Standard library imports
import re
import logging
from datetime import datetime, UTC
from pydantic import BaseModel

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException

# Local imports
import analytiq_data as ad
from docrouter_app.auth import get_admin_user
from docrouter_app.models import User

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
aws_router = APIRouter(tags=["account/aws"])

# AWS models
class AWSConfig(BaseModel):
    access_key_id: str
    secret_access_key: str
    s3_bucket_name: str

# AWS management endpoints
@aws_router.post("/v0/account/aws_config")
async def create_aws_config(
    config: AWSConfig,
    current_user: User = Depends(get_admin_user)
):  
    """Create or update AWS configuration (admin only)"""
    db = ad.common.get_async_db()
    # Validate all fields are non-empty
    if not config.access_key_id or not config.access_key_id.strip():
        raise HTTPException(
            status_code=400,
            detail="AWS Access Key ID is required and cannot be empty"
        )
    
    if not config.secret_access_key or not config.secret_access_key.strip():
        raise HTTPException(
            status_code=400,
            detail="AWS Secret Access Key is required and cannot be empty"
        )
    
    if not config.s3_bucket_name or not config.s3_bucket_name.strip():
        raise HTTPException(
            status_code=400,
            detail="S3 Bucket Name is required and cannot be empty"
        )

    # Validate AWS Access Key ID format
    if not re.match(r'^[A-Z0-9]{20}$', config.access_key_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid AWS Access Key ID format. Must be 20 characters long and contain only uppercase letters and numbers."
        )

    # Validate AWS Secret Access Key format
    if not re.match(r'^[A-Za-z0-9+/]{40}$', config.secret_access_key):
        raise HTTPException(
            status_code=400,
            detail="Invalid AWS Secret Access Key format. Must be 40 characters long and contain only letters, numbers, and +/."
        )

    encrypted_access_key = ad.crypto.encrypt_token(config.access_key_id)
    encrypted_secret_key = ad.crypto.encrypt_token(config.secret_access_key)
    
    update_data = {
        "access_key_id": encrypted_access_key,
        "secret_access_key": encrypted_secret_key,
        "s3_bucket_name": config.s3_bucket_name,
        "created_at": datetime.now(UTC)
    }

    await db.aws_config.update_one(
        {"user_id": current_user.user_id},
        {"$set": update_data},
        upsert=True
    )
    
    return {"message": "AWS configuration saved successfully"}

@aws_router.get("/v0/account/aws_config")
async def get_aws_config(current_user: User = Depends(get_admin_user)):
    """Get AWS configuration (admin only)"""
    db = ad.common.get_async_db()
    config = await db.aws_config.find_one({"user_id": current_user.user_id})
    if not config:
        raise HTTPException(status_code=404, detail="AWS configuration not found")
        
    return {
        "access_key_id": ad.crypto.decrypt_token(config["access_key_id"]),
        "secret_access_key": ad.crypto.decrypt_token(config["secret_access_key"]),
        "s3_bucket_name": config.get("s3_bucket_name")
    }

@aws_router.delete("/v0/account/aws_config")
async def delete_aws_config(current_user: User = Depends(get_admin_user)):
    """Delete AWS configuration (admin only)"""
    db = ad.common.get_async_db()
    result = await db.aws_config.delete_one({"user_id": current_user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="AWS configuration not found")
    return {"message": "AWS configuration deleted successfully"}
