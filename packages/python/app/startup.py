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
        
        # Require configured admin email so we only seed after initial admin bootstrap.
        admin_email = os.getenv("ADMIN_EMAIL")
        if not admin_email:
            return
        if not await db.users.find_one({"email": admin_email}):
            return

        # AWS Configuration. Only store global deployment config if it doesn't already exist.
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        aws_s3_bucket = os.getenv("AWS_S3_BUCKET_NAME", "")

        existing_aws = await db.cloud_config.find_one({"type": "aws"})

        if not existing_aws:
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
                "type": "aws",
                "access_key_id": encrypted_access_key,
                "secret_access_key": encrypted_secret_key,
                "s3_bucket_name": aws_s3_bucket,
                "created_at": datetime.now(UTC),
            }

            await db.cloud_config.update_one(
                {"type": "aws"},
                {"$set": update_data, "$unset": {"user_id": ""}},
                upsert=True,
            )
            logger.info("AWS global configuration stored in cloud_config from environment")

        # Azure service principal (cloud_config type azure). Only store if not already saved from the UI.
        azure_tenant_id = os.getenv("AZURE_TENANT_ID", "")
        azure_client_id = os.getenv("AZURE_CLIENT_ID", "")
        azure_client_secret = os.getenv("AZURE_CLIENT_SECRET", "")
        azure_api_base = (os.getenv("AZURE_API_BASE", "") or "").strip().rstrip("/")

        existing_azure = await db.cloud_config.find_one({"type": ad.cloud.TYPE_AZURE})

        if not existing_azure:
            if len(azure_tenant_id.strip()) == 0:
                logger.warning("AZURE_TENANT_ID environment variable not set")
            if len(azure_client_id.strip()) == 0:
                logger.warning("AZURE_CLIENT_ID environment variable not set")
            if len(azure_client_secret.strip()) == 0:
                logger.warning("AZURE_CLIENT_SECRET environment variable not set")
            if not azure_api_base:
                logger.warning(
                    "AZURE_API_BASE environment variable not set (Foundry endpoint URL)"
                )

            encrypted_tenant = ad.crypto.encrypt_token(azure_tenant_id)
            encrypted_client = ad.crypto.encrypt_token(azure_client_id)
            encrypted_secret = ad.crypto.encrypt_token(azure_client_secret)

            azure_update = {
                "type": ad.cloud.TYPE_AZURE,
                "tenant_id": encrypted_tenant,
                "client_id": encrypted_client,
                "client_secret": encrypted_secret,
                "api_base": azure_api_base,
                "created_at": datetime.now(UTC),
            }

            await db.cloud_config.update_one(
                {"type": ad.cloud.TYPE_AZURE},
                {"$set": azure_update, "$unset": {"user_id": ""}},
                upsert=True,
            )
            logger.info(
                "Azure global service principal stored in cloud_config from environment"
            )

    except Exception as e:
        logger.error(f"Failed to set up API credentials: {e}")