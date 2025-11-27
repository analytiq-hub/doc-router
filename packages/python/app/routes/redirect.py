# redirect.py

# Standard library imports
import os
import logging

# Third-party imports
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
redirect_router = APIRouter()

# Environment variables
NEXTAUTH_URL = os.getenv("NEXTAUTH_URL")
if not NEXTAUTH_URL:
    raise ValueError("NEXTAUTH_URL is not set")


@redirect_router.get("/", include_in_schema=False)
async def root():
    """Redirect root URL to frontend"""
    frontend_url = NEXTAUTH_URL
    return RedirectResponse(url=frontend_url)


@redirect_router.get("/settings/user/developer/organization-access-tokens", include_in_schema=False)
async def redirect_organization_access_tokens():
    """Redirect organization access tokens URL to frontend"""
    frontend_url = NEXTAUTH_URL
    return RedirectResponse(url=f"{frontend_url}/settings/user/developer/organization-access-tokens")


