# oauth.py

# Standard library imports
import json
import hmac
import hashlib
import logging
import os
from datetime import datetime, UTC
from typing import Optional, Literal

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

# Local imports
import analytiq_data as ad
from app.routes.payments import sync_customer

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
oauth_router = APIRouter()

# OAuth models
class OAuthAccountData(BaseModel):
    type: str = "oauth"
    access_token: Optional[str] = None
    expires_at: Optional[int] = None
    token_type: Optional[str] = None
    scope: Optional[str] = None
    id_token: Optional[str] = None
    refresh_token: Optional[str] = None

class OAuthSignInRequest(BaseModel):
    email: str = Field(..., description="User email address")
    name: Optional[str] = Field(None, description="User's full name")
    email_verified: bool = Field(False, description="Whether email is verified")
    provider: Literal["google", "github"] = Field(..., description="OAuth provider")
    provider_account_id: str = Field(..., description="Provider's unique account ID")
    account: OAuthAccountData = Field(..., description="OAuth account data")

class OAuthSignInResponse(BaseModel):
    success: bool
    user_id: str
    is_new_user: bool

# Environment variables
NEXTAUTH_SECRET = os.getenv("NEXTAUTH_SECRET")

# OAuth endpoints
@oauth_router.post("/v0/account/auth/oauth", response_model=OAuthSignInResponse, tags=["account/auth"])
async def oauth_signin(request: Request):
    """
    Handle OAuth sign-in from NextAuth.
    Creates/links user, account, organization, and syncs with Stripe.
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
        logger.warning(f"Invalid signature for OAuth request")
        raise HTTPException(
            status_code=401,
            detail="Invalid request signature"
        )

    # Parse and validate the request body after signature verification
    try:
        oauth_data = json.loads(raw_body)
        oauth_request = OAuthSignInRequest(**oauth_data)
    except (json.JSONDecodeError, Exception) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request body: {str(e)}"
        )

    logger.info(f"oauth_signin(): email={oauth_request.email}, provider={oauth_request.provider}")

    # Process OAuth sign-in
    db = ad.common.get_async_db()

    try:
        # Check if user already exists
        existing_user = await db.users.find_one({"email": oauth_request.email})

        if existing_user:
            user_id = str(existing_user["_id"])
            is_new_user = False
            logger.info(f"Existing user found: {user_id}")

            # Check if this OAuth account already exists
            existing_account = await db.accounts.find_one({
                "provider": oauth_request.provider,
                "providerAccountId": oauth_request.provider_account_id
            })

            if not existing_account:
                # Link OAuth account to existing user
                await db.accounts.insert_one({
                    "userId": user_id,
                    "type": oauth_request.account.type,
                    "provider": oauth_request.provider,
                    "providerAccountId": oauth_request.provider_account_id,
                    "access_token": oauth_request.account.access_token,
                    "expires_at": oauth_request.account.expires_at,
                    "token_type": oauth_request.account.token_type,
                    "scope": oauth_request.account.scope,
                    "id_token": oauth_request.account.id_token,
                    "refresh_token": oauth_request.account.refresh_token
                })
                logger.info(f"Linked {oauth_request.provider} account to existing user {user_id}")
        else:
            # Create new user
            is_new_user = True
            user_result = await db.users.insert_one({
                "email": oauth_request.email,
                "name": oauth_request.name,
                "role": "user",
                "email_verified": oauth_request.email_verified,
                "created_at": datetime.now(UTC)
            })
            user_id = str(user_result.inserted_id)
            logger.info(f"Created new user: {user_id}")

            # Create OAuth account record
            await db.accounts.insert_one({
                "userId": user_id,
                "type": oauth_request.account.type,
                "provider": oauth_request.provider,
                "providerAccountId": oauth_request.provider_account_id,
                "access_token": oauth_request.account.access_token,
                "expires_at": oauth_request.account.expires_at,
                "token_type": oauth_request.account.token_type,
                "scope": oauth_request.account.scope,
                "id_token": oauth_request.account.id_token,
                "refresh_token": oauth_request.account.refresh_token
            })
            logger.info(f"Created {oauth_request.provider} account for user {user_id}")

            # Create individual organization using email as name
            org_result = await db.organizations.insert_one({
                "name": oauth_request.email,
                "type": "individual",
                "members": [{
                    "user_id": user_id,
                    "role": "admin"
                }],
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC)
            })
            org_id = str(org_result.inserted_id)
            logger.info(f"Created organization {org_id} for user {user_id}")

            # Sync with Stripe
            try:
                await sync_customer(db=db, org_id=org_id)
                logger.info(f"Successfully synced organization {org_id} with Stripe")
            except Exception as e:
                logger.warning(f"Failed to sync organization {org_id} with Stripe: {e}")
                # Don't fail the sign-in if Stripe sync fails

        return OAuthSignInResponse(
            success=True,
            user_id=user_id,
            is_new_user=is_new_user
        )

    except Exception as e:
        logger.error(f"Error in oauth_signin: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process OAuth sign-in: {str(e)}"
        )
