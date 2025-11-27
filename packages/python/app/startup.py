import sys, os
from datetime import datetime, UTC
from bcrypt import hashpw, gensalt
from bson import ObjectId
import logging

# Set up the path
cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{cwd}/..")

import analytiq_data as ad

logger = logging.getLogger(__name__)

async def setup_database(analytiq_client):
    """Set up database and run migrations"""
    try:
        await ad.migrations.run_migrations(analytiq_client)
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise

async def setup_admin(analytiq_client):
    """
    Create admin user during application startup if it doesn't exist
    """
    # Get environment
    env = analytiq_client.env

    # Get admin email and password from environment variables
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    
    if not admin_email or not admin_password:
        return

    # Run migrations
    await setup_database(analytiq_client)

    try:
        db = analytiq_client.mongodb_async[env]
        
        # Initialize LLM models
        await ad.llm.providers.setup_llm_providers(analytiq_client)
        
        users = db.users
        
        # Check if admin already exists
        existing_admin = await users.find_one({"email": admin_email})
        if existing_admin:
            return
            
        # Create admin user with bcrypt hash
        hashed_password = hashpw(admin_password.encode(), gensalt(12))
        result = await users.insert_one({
            "email": admin_email,
            "password": hashed_password.decode(),
            "name": "System Administrator",
            "role": "admin",
            "email_verified": True,
            "created_at": datetime.now(UTC)
        })
        
        admin_id = str(result.inserted_id)
        
        # Create organization for admin
        await db.organizations.insert_one({
            "_id": ObjectId(admin_id),
            "name": "Admin",
            "type": "individual",
            "members": [{
                "user_id": admin_id,
                "role": "admin"
            }],
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            "has_seen_tour": False
        })
        
        logger.info(f"Created default admin user: {admin_email}")
    except Exception as e:
        logger.error(f"Failed to create default admin: {e}")

async def setup_api_creds(analytiq_client):
    """
    Set up API credentials for various services during startup
    """
    try:
        env = analytiq_client.env
        db = analytiq_client.mongodb_async[env]
        
        # Get system admin user
        admin_email = os.getenv("ADMIN_EMAIL")
        if not admin_email:
            return
            
        admin_user = await db.users.find_one({"email": admin_email})
        if not admin_user:
            return
            
        admin_id = str(admin_user["_id"])
        
        # AWS Configuration. Only store configuration if it doesn't already exist.
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        aws_s3_bucket = os.getenv("AWS_S3_BUCKET_NAME", "")
        
        existing_aws_config = await db.aws_config.find_one({"user_id": admin_id})

        if not existing_aws_config:
            # Check if .env has all the required AWS configuration
            if len(aws_access_key) == 0:
                logger.warning("AWS_ACCESS_KEY_ID environment variable not set")
            if len(aws_secret_key) == 0:
                logger.warning("AWS_SECRET_ACCESS_KEY environment variable not set")
            if len(aws_s3_bucket) == 0:
                logger.warning("AWS_S3_BUCKET_NAME environment variable not set")

            # Encrypt configuration before storing
            encrypted_access_key = ad.crypto.encrypt_token(aws_access_key)
            encrypted_secret_key = ad.crypto.encrypt_token(aws_secret_key)
            
            update_data = {
                "access_key_id": encrypted_access_key,
                "secret_access_key": encrypted_secret_key,
                "s3_bucket_name": aws_s3_bucket,
                "created_at": datetime.now(UTC)
            }
            
            await db.aws_config.update_one(
                {"user_id": admin_id},
                {"$set": update_data},
                upsert=True
            )
            logger.info("AWS configuration configured for admin user")
            
    except Exception as e:
        logger.error(f"Failed to set up API credentials: {e}")