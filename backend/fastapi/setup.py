import sys, os
from datetime import datetime, UTC
from bcrypt import hashpw, gensalt
from bson import ObjectId

# Set up the path
cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{cwd}/..")

import analytiq_data as ad

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
        
    try:
        db = analytiq_client.mongodb_async[env]
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
            "emailVerified": True,
            "createdAt": datetime.now(UTC)
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
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        ad.log.info(f"Created default admin user: {admin_email}")
    except Exception as e:
        ad.log.error(f"Failed to create default admin: {e}")

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
        
        # AWS Credentials. Only store credentials if they don't already exist.
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        existing_aws_creds = await db.aws_credentials.find_one({"user_id": admin_id})
        
        if aws_access_key != "" and aws_secret_key != "" and not existing_aws_creds:
            # Encrypt credentials before storing
            encrypted_access_key = ad.crypto.encrypt_token(aws_access_key)
            encrypted_secret_key = ad.crypto.encrypt_token(aws_secret_key)
            
            await db.aws_credentials.update_one(
                {"user_id": admin_id},
                {
                    "$set": {
                        "access_key_id": encrypted_access_key,
                        "secret_access_key": encrypted_secret_key,
                        "created_at": datetime.now(UTC)
                    }
                },
                upsert=True
            )
            ad.log.info("AWS credentials configured for admin user")
            
        # LLM API Keys
        llm_credentials = []
        
        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key != "":
            llm_credentials.append(("OpenAI", openai_key))
            
        # Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if anthropic_key != "":
            llm_credentials.append(("Anthropic", anthropic_key))
            
        # Groq
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key != "":
            llm_credentials.append(("Groq", groq_key))
            
        # Store LLM credentials
        for vendor, api_key in llm_credentials:
            # Only store credentials if they don't already exist
            existing_llm_creds = await db.llm_tokens.find_one({"user_id": admin_id, "llm_vendor": vendor})
            if existing_llm_creds:
                continue
                
            encrypted_key = ad.crypto.encrypt_token(api_key)
            await db.llm_tokens.update_one(
                {
                    "user_id": admin_id,
                    "llm_vendor": vendor
                },
                {
                    "$set": {
                        "token": encrypted_key,
                        "created_at": datetime.now(UTC)
                    }
                },
                upsert=True
            )
            ad.log.info(f"{vendor} API key configured for admin user")
            
    except Exception as e:
        ad.log.error(f"Failed to set up API credentials: {e}")