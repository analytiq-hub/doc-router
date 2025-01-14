# main.py

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Depends, status, Body, Security, Response, BackgroundTasks
from fastapi.encoders import jsonable_encoder  # Add this import
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timedelta, UTC
from jose import JWTError, jwt
from typing import Optional, List
import os
import sys
import json
from dotenv import load_dotenv
import secrets
import base64
import io
import re
import uuid
import logging
import hmac
import hashlib
from bcrypt import hashpw, gensalt
import asyncio
from email_utils import get_verification_email_content, get_email_subject, get_invitation_email_content

import setup
import organizations
from schemas import (
    User,
    AccessToken, ListAccessTokensResponse, CreateAccessTokenRequest,
    ListDocumentsResponse,
    DocumentMetadata,
    DocumentUpload, DocumentsUpload, DocumentUpdate,
    LLMToken, CreateLLMTokenRequest, ListLLMTokensResponse,
    AWSCredentials,
    OCRMetadataResponse,
    LLMRunResponse, LLMResult,
    Schema, SchemaCreate, ListSchemasResponse,
    Prompt, PromptCreate, ListPromptsResponse,
    TagCreate, Tag, ListTagsResponse,
    DocumentResponse,
    UserCreate, UserUpdate, UserResponse, ListUsersResponse,
    OrganizationMember,
    OrganizationCreate,
    OrganizationUpdate,
    Organization,
    ListOrganizationsResponse,
    InvitationResponse,
    CreateInvitationRequest,
    ListInvitationsResponse,
    AcceptInvitationRequest,
    SaveFlowRequest,
    Flow,
    ListFlowsResponse, FlowMetadata
)

from routes import (
    account_llm_tokens_router,
    account_aws_credentials_router,
    account_organizations_router,
    account_users_router,
    account_email_router,
    access_tokens_router,
    documents_router,
    flows_router,
    llm_router,
    ocr_router,
    schemas_router,
    prompts_router,
    tags_router
)

# Set up the path
cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{cwd}/..")

import analytiq_data as ad
import users
import limits

# Set up the environment variables. This reads the .env file.
ad.common.setup()

# Environment variables
ENV = os.getenv("ENV", "dev")
NEXTAUTH_URL = os.getenv("NEXTAUTH_URL")
FASTAPI_ROOT_PATH = os.getenv("FASTAPI_ROOT_PATH", "/")
MONGODB_URI = os.getenv("MONGODB_URI")
SES_FROM_EMAIL = os.getenv("SES_FROM_EMAIL")

ad.log.info(f"ENV: {ENV}")
ad.log.info(f"NEXTAUTH_URL: {NEXTAUTH_URL}")
ad.log.info(f"FASTAPI_ROOT_PATH: {FASTAPI_ROOT_PATH}")
ad.log.info(f"MONGODB_URI: {MONGODB_URI}")
ad.log.info(f"SES_FROM_EMAIL: {SES_FROM_EMAIL}")
# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
UPLOAD_DIR = "data"

from setup import get_async_db, get_analytiq_client
from auth import get_current_user, get_admin_user

# Initialize globals first (instead of dependencies)
setup.setup_globals(env=ENV)

app = FastAPI(
    root_path=FASTAPI_ROOT_PATH,
)

# Add routes
app.include_router(documents_router)
app.include_router(access_tokens_router)
app.include_router(ocr_router)
app.include_router(llm_router)
app.include_router(flows_router)
app.include_router(schemas_router)
app.include_router(prompts_router)
app.include_router(tags_router)
app.include_router(account_llm_tokens_router)
app.include_router(account_aws_credentials_router)
app.include_router(account_organizations_router)
app.include_router(account_users_router)
app.include_router(account_email_router)

security = HTTPBearer()

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    NEXTAUTH_URL,
]

ad.log.info(f"CORS allowed origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"] # Needed to expose the Content-Disposition header to the frontend
)

# Get db reference if needed
db = get_async_db()

# Get analytiq client reference
analytiq_client = get_analytiq_client()

# MongoDB collections - these can stay as they reference the db variable above
job_queue_collection = db.job_queue
access_token_collection = db.access_tokens
llm_token_collection = db.llm_tokens
aws_credentials_collection = db.aws_credentials
schemas_collection = db.schemas
schema_versions_collection = db.schema_versions
prompts_collection = db.prompts
prompt_versions_collection = db.prompt_versions
tags_collection = db.tags
organizations_collection = db.organizations

from pydantic import BaseModel

# Add to startup
@app.on_event("startup")
async def startup_event():
    await setup.setup_admin(analytiq_client)
    await setup.setup_api_creds(analytiq_client)

@app.post("/auth/token")
async def create_auth_token(user_data: dict = Body(...)):
    """Create an authentication token"""
    ad.log.debug(f"create_auth_token(): user_data: {user_data}")
    token = jwt.encode(
        {
            "userId": user_data["id"],
            "userName": user_data["name"],
            "email": user_data["email"]
        },
        FASTAPI_SECRET,
        algorithm=ALGORITHM
    )
    return {"token": token}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="::", port=8000)
