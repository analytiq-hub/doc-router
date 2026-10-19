# oauth.py

# Standard library imports
import json
import hmac
import hashlib
import logging
import os

# Third-party imports
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

# Local imports
from app.account.oauth_models import OAuthSignInRequest
from app.account.oauth_provision import provision_oauth_signin

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
oauth_router = APIRouter()

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
    Legacy HMAC hook (deprecated; browser OAuth uses ``account_auth`` callbacks).
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

    try:
        user_id, is_new_user = await provision_oauth_signin(oauth_request)
        return OAuthSignInResponse(
            success=True,
            user_id=user_id,
            is_new_user=is_new_user,
        )
    except Exception as e:
        logger.error(f"Error in oauth_signin: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process OAuth sign-in: {str(e)}",
        )
