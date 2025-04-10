# main.py

# Standard library imports
from datetime import datetime, timedelta, UTC
import os
import sys
import json
import secrets
import base64
import re
import uuid
import logging
import hmac
import hashlib
import asyncio
from typing import Optional, List
from contextlib import asynccontextmanager

# Set up the path first, before other imports
cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{cwd}/..")

# Third-party imports
from fastapi import (
    FastAPI, File, UploadFile, HTTPException, Query, 
    Depends, status, Body, Security, Response, 
    BackgroundTasks, Request
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from jose import JWTError, jwt
from bcrypt import hashpw, gensalt
from dotenv import load_dotenv
from jsonschema import validate, ValidationError, Draft7Validator

# Local imports
from api import email_utils, startup, organizations, users, limits
from api.schemas import (
    User, AccessToken, ListAccessTokensResponse,
    CreateAccessTokenRequest, ListDocumentsResponse,
    DocumentMetadata, DocumentUpload, DocumentsUpload,
    DocumentUpdate,
    LLMModel, ListLLMModelsResponse,
    LLMToken, CreateLLMTokenRequest, ListLLMTokensResponse,
    AWSCredentials,
    GetOCRMetadataResponse,
    LLMRunResponse,
    LLMResult,
    UpdateLLMResultRequest,
    Schema, SchemaConfig, ListSchemasResponse,
    Prompt, PromptConfig, ListPromptsResponse,
    TagConfig, Tag, ListTagsResponse,
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
    FlowConfig,
    Flow,
    ListFlowsResponse, FlowMetadata
)
from api.payments import router as payments_router
from api.payments import (
    init_payments,
    get_or_create_payments_customer,
    update_payments_customer,
    delete_payments_customer
)
import analytiq_data as ad

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
FASTAPI_SECRET = os.getenv("FASTAPI_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Define MongoDB connection check function to be used in lifespan
async def check_mongodb_connection(uri):
    try:
        # Create a MongoDB client
        mongo_client = AsyncIOMotorClient(uri)
        
        # The ismaster command is cheap and does not require auth
        await mongo_client.admin.command('ismaster')
        ad.log.info(f"MongoDB connection successful at {uri}")
        return True
    except Exception as e:
        ad.log.error(f"Failed to connect to MongoDB at {uri}: {e}")
        return False

UPLOAD_DIR = "data"

# Create the FastAPI app with the lifespan
app = FastAPI(
    root_path=FASTAPI_ROOT_PATH,
)
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

# Add this helper to get API context
def get_api_context(path: str) -> tuple[str, Optional[str]]:
    """
    Parse the API path to determine context (account vs org) and org_id if present.
    Returns (context_type, organization_id)
    """
    parts = path.split('/')
    if parts[1] == "account":
        return "account", None
    elif parts[1] == "orgs" and len(parts) > 2:
        return "organization", parts[2]
    return "unknown", None

# Modify get_current_user to validate based on context
async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security), request: Request = None):
    """
    Validate user based on JWT or API token, considering the API context.
    Account APIs only accept account-level tokens.
    Organization APIs only accept org-specific tokens for that organization.
    """
    db = ad.common.get_async_db()
    token = credentials.credentials
    
    # Get API context
    context_type, org_id = get_api_context(request.url.path)
    
    try:
        # First, try to validate as JWT (always valid for both contexts)
        payload = jwt.decode(token, FASTAPI_SECRET, algorithms=[ALGORITHM])
        userId: str = payload.get("userId")
        userName: str = payload.get("userName")
        email: str = payload.get("email")
        
        if userName is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        # Validate that userId exists in database
        user = await db.users.find_one({"_id": ObjectId(userId)})
        if not user:
            raise HTTPException(status_code=401, detail="User not found in database")

        # TO DO: Validate that the user is a member of the organization
        # if org_id:
        #     org_member = await db.org_members.find_one({
        #         "user_id": userId,
        #         "organization_id": org_id
        #     })
        #     if not org_member:
        #         raise HTTPException(status_code=401, detail="User not a member of organization")
            
        return User(
            user_id=userId,
            user_name=userName,
            token_type="jwt"
        )
                   
    except JWTError:
        # If JWT validation fails, check if it's an API token
        encrypted_token = ad.crypto.encrypt_token(token)
        
        # Build query based on context
        token_query = {"token": encrypted_token}
        
        if context_type == "account":
            # For account APIs, only accept account-level tokens
            token_query["organization_id"] = None
        elif context_type == "organization" and org_id:
            # For org APIs, only accept tokens for that specific org
            token_query["organization_id"] = org_id
        else:
            raise HTTPException(status_code=401, detail="Invalid API context")
            
        stored_token = await db.access_tokens.find_one(token_query)
        
        if stored_token:
            # Validate that user_id from stored token exists in database
            user = await db.users.find_one({"_id": ObjectId(stored_token["user_id"])})
            if not user:
                raise HTTPException(status_code=401, detail="User not found in database")
                
            return User(
                user_id=stored_token["user_id"],
                user_name=stored_token["name"],
                token_type="api"
            )
                
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

# Add this helper function to check admin status
async def get_admin_user(credentials: HTTPAuthorizationCredentials = Security(security), request: Request = None):
    user = await get_current_user(credentials, request)
    db = ad.common.get_async_db()

    # Check if user has admin role in database
    db_user = await db.users.find_one({"_id": ObjectId(user.user_id)})
    if not db_user or db_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return user

# Organization-level access tokens
@app.post("/v0/orgs/{organization_id}/access_tokens", response_model=AccessToken, tags=["access_tokens"])
async def create_org_token(
    organization_id: str,
    request: CreateAccessTokenRequest,
    current_user: User = Depends(get_current_user)
):
    """Create an organization-level API token"""
    # First verify organization membership
    org_id = await get_current_org(current_user, organization_id)
    
    db = ad.common.get_async_db()
    token = secrets.token_urlsafe(32)
    new_token = {
        "user_id": current_user.user_id,
        "organization_id": org_id,
        "name": request.name,
        "token": ad.crypto.encrypt_token(token),
        "created_at": datetime.now(UTC),
        "lifetime": request.lifetime
    }
    result = await db.access_tokens.insert_one(new_token)

    new_token["token"] = token  # Return plaintext token to user
    new_token["id"] = str(result.inserted_id)
    return new_token

@app.get("/v0/orgs/{organization_id}/access_tokens", response_model=ListAccessTokensResponse, tags=["access_tokens"])
async def list_org_tokens(
    organization_id: str,
    current_user: User = Depends(get_current_user)
):
    """List organization-level API tokens"""
    # First verify organization membership
    org_id = await get_current_org(current_user, organization_id)
    
    db = ad.common.get_async_db()
    cursor = db.access_tokens.find({
        "user_id": current_user.user_id,
        "organization_id": org_id
    })
    tokens = await cursor.to_list(length=None)
    ret = [
        {
            "id": str(token["_id"]),
            "user_id": token["user_id"],
            "organization_id": token["organization_id"],
            "name": token["name"],
            "token": token["token"],
            "created_at": token["created_at"],
            "lifetime": token["lifetime"]
        }
        for token in tokens
    ]
    return ListAccessTokensResponse(access_tokens=ret)

@app.delete("/v0/orgs/{organization_id}/access_tokens/{token_id}", tags=["access_tokens"])
async def delete_org_token(
    organization_id: str,
    token_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete an organization-level API token"""
    # First verify organization membership
    org_id = await get_current_org(current_user, organization_id)
    
    db = ad.common.get_async_db()
    result = await db.access_tokens.delete_one({
        "_id": ObjectId(token_id),
        "user_id": current_user.user_id,
        "organization_id": org_id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token deleted successfully"}


# PDF management endpoints
@app.post("/v0/orgs/{organization_id}/documents", tags=["documents"])
async def upload_document(
    organization_id: str,
    documents_upload: DocumentsUpload = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Upload one or more documents"""
    ad.log.debug(f"upload_document(): documents: {[doc.name for doc in documents_upload.documents]}")
    uploaded_documents = []

    # Validate all tag IDs first
    all_tag_ids = set()
    for document in documents_upload.documents:
        all_tag_ids.update(document.tag_ids)

    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    
    if all_tag_ids:
        # Check if all tags exist and belong to the organization
        tags_cursor = db.tags.find({
            "_id": {"$in": [ObjectId(tag_id) for tag_id in all_tag_ids]},
            "organization_id": organization_id
        })
        existing_tags = await tags_cursor.to_list(None)
        existing_tag_ids = {str(tag["_id"]) for tag in existing_tags}
        
        invalid_tags = all_tag_ids - existing_tag_ids
        if invalid_tags:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tag IDs: {list(invalid_tags)}"
            )

    for document in documents_upload.documents:
        if not document.name.endswith('.pdf'):
            raise HTTPException(status_code=400, detail=f"Document {document.name} is not a PDF")
        
        # Decode and save the document
        content = base64.b64decode(document.content.split(',')[1])

        # Create a unique id for the document
        document_id = ad.common.create_id()
        mongo_file_name = f"{document_id}.pdf"

        metadata = {
            "document_id": document_id,
            "type": "application/pdf",
            "size": len(content),
            "user_file_name": document.name
        }

        # Save the document to mongodb
        await ad.common.save_file_async(analytiq_client,
                                        file_name=mongo_file_name,
                                        blob=content,
                                        metadata=metadata)

        document_metadata = {
            "_id": ObjectId(document_id),
            "user_file_name": document.name,
            "mongo_file_name": mongo_file_name,
            "document_id": document_id,
            "upload_date": datetime.now(UTC),
            "uploaded_by": current_user.user_name,
            "state": ad.common.doc.DOCUMENT_STATE_UPLOADED,
            "tag_ids": document.tag_ids,
            "organization_id": organization_id  # Add organization_id
        }
        
        await ad.common.save_doc(analytiq_client, document_metadata)
        uploaded_documents.append({
            "document_name": document.name,
            "document_id": document_id,
            "tag_ids": document.tag_ids
        })

        # Post a message to the ocr job queue
        msg = {"document_id": document_id}
        await ad.queue.send_msg(analytiq_client, "ocr", msg=msg)
    
    return {"uploaded_documents": uploaded_documents}

@app.put("/v0/orgs/{organization_id}/documents/{document_id}", tags=["documents"])
async def update_document(
    organization_id: str,
    document_id: str,
    update: DocumentUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update a document"""
    ad.log.debug(f"Updating document {document_id} with data: {update}")
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)

    # Validate the document exists and belongs to the organization
    document = await db.docs.find_one({
        "_id": ObjectId(document_id),
        "organization_id": organization_id
    })
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Validate all tag IDs
    if update.tag_ids:
        tags_cursor = db.tags.find({
            "_id": {"$in": [ObjectId(tag_id) for tag_id in update.tag_ids]},
            "organization_id": organization_id
        })
        existing_tags = await tags_cursor.to_list(None)
        existing_tag_ids = {str(tag["_id"]) for tag in existing_tags}
        
        invalid_tags = set(update.tag_ids) - existing_tag_ids
        if invalid_tags:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tag IDs: {list(invalid_tags)}"
            )
    
    # Prepare update dictionary
    update_dict = {}
    if update.tag_ids:
        update_dict["tag_ids"] = update.tag_ids
    
    # Add document_name to update if provided
    if update.document_name is not None:
        update_dict["user_file_name"] = update.document_name
    
    # Only proceed if there's something to update
    if not update_dict:
        return {"message": "No updates provided"}

    # Update the document
    updated_doc = await db.docs.find_one_and_update(
        {
            "_id": ObjectId(document_id),
            "organization_id": organization_id
        },
        {"$set": update_dict},
        return_document=True
    )

    if not updated_doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    return {"message": "Document updated successfully"}


@app.get("/v0/orgs/{organization_id}/documents", response_model=ListDocumentsResponse, tags=["documents"])
async def list_documents(
    organization_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    tag_ids: str = Query(None, description="Comma-separated list of tag IDs"),
    user: User = Depends(get_current_user)
):
    """List documents within an organization"""
    # Get analytiq client
    analytiq_client = ad.common.get_analytiq_client()
    
    # Get documents from database with organization scope
    documents, total_count = await ad.common.list_docs(
        analytiq_client, 
        organization_id=organization_id,
        skip=skip, 
        limit=limit
    )
    
    # Add tag filtering if tag_ids are provided
    if tag_ids:
        tag_id_list = [tid.strip() for tid in tag_ids.split(",")]
        documents = [doc for doc in documents if all(tid in doc.get("tag_ids", []) for tid in tag_id_list)]
        total_count = len(documents)
    
    return ListDocumentsResponse(
        documents=[
            {
                "id": str(doc["_id"]),
                "document_name": doc["user_file_name"],
                "upload_date": doc["upload_date"].isoformat(),
                "uploaded_by": doc["uploaded_by"],
                "state": doc.get("state", ""),
                "tag_ids": doc.get("tag_ids", [])
            }
            for doc in documents
        ],
        total_count=total_count,
        skip=skip
    )

@app.get("/v0/orgs/{organization_id}/documents/{document_id}", response_model=DocumentResponse, tags=["documents"])
async def get_document(
    organization_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a document"""
    ad.log.debug(f"get_document() start: document_id: {document_id}")
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)

    # Get document with organization scope
    document = await db.docs.find_one({
        "_id": ObjectId(document_id),
        "organization_id": organization_id
    })
    
    if not document:
        ad.log.debug(f"get_document() document not found: {document}")
        raise HTTPException(status_code=404, detail="Document not found")
        
    ad.log.debug(f"get_document() found document: {document}")

    # Get the file from mongodb
    file = ad.common.get_file(analytiq_client, document["mongo_file_name"])
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")

    ad.log.debug(f"get_document() got file: {document}")

    # Create metadata response
    metadata = DocumentMetadata(
        id=str(document["_id"]),
        document_name=document["user_file_name"],
        upload_date=document["upload_date"],
        uploaded_by=document["uploaded_by"],
        state=document.get("state", ""),
        tag_ids=document.get("tag_ids", [])
    )

    # Return using the DocumentResponse model
    return DocumentResponse(
        metadata=metadata,
        content=base64.b64encode(file["blob"]).decode('utf-8')
    )

@app.delete("/v0/orgs/{organization_id}/documents/{document_id}", tags=["documents"])
async def delete_document(
    organization_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a document"""
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)

    # Get document with organization scope
    document = await db.docs.find_one({
        "_id": ObjectId(document_id),
        "organization_id": organization_id
    })
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if "mongo_file_name" not in document:
        raise HTTPException(
            status_code=500, 
            detail="Document metadata is corrupted: missing mongo_file_name"
        )

    await ad.common.delete_file_async(analytiq_client, file_name=document["mongo_file_name"])
    await ad.common.delete_doc(analytiq_client, document_id, organization_id)
    
    return {"message": "Document deleted successfully"}

@app.get("/v0/orgs/{organization_id}/ocr/download/blocks/{document_id}", tags=["ocr"])
async def download_ocr_blocks(
    organization_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """Download OCR blocks for a document"""
    ad.log.debug(f"download_ocr_blocks() start: document_id: {document_id}")
    analytiq_client = ad.common.get_analytiq_client()

    document = await ad.common.get_doc(analytiq_client, document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get the OCR JSON data from mongodb
    ocr_json = ad.common.get_ocr_json(analytiq_client, document_id)
    if ocr_json is None:
        raise HTTPException(status_code=404, detail="OCR data not found")
    
    return JSONResponse(content=ocr_json)

@app.get("/v0/orgs/{organization_id}/ocr/download/text/{document_id}", response_model=str, tags=["ocr"])
async def download_ocr_text(
    organization_id: str,
    document_id: str,
    page_num: Optional[int] = Query(None, description="Specific page number to retrieve"),
    current_user: User = Depends(get_current_user)
):
    """Download OCR text for a document"""
    ad.log.debug(f"download_ocr_text() start: document_id: {document_id}, page_num: {page_num}")
    
    analytiq_client = ad.common.get_analytiq_client()
    document = await ad.common.get_doc(analytiq_client, document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Page number is 1-based, but the OCR text page_idx is 0-based
    page_idx = None
    if page_num is not None:
        page_idx = page_num - 1

    # Get the OCR text data from mongodb
    text = ad.common.get_ocr_text(analytiq_client, document_id, page_idx)
    if text is None:
        raise HTTPException(status_code=404, detail="OCR text not found")
    
    return Response(content=text, media_type="text/plain")

@app.get("/v0/orgs/{organization_id}/ocr/download/metadata/{document_id}", response_model=GetOCRMetadataResponse, tags=["ocr"])
async def get_ocr_metadata(
    organization_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get OCR metadata for a document"""
    ad.log.debug(f"get_ocr_metadata() start: document_id: {document_id}")
    
    analytiq_client = ad.common.get_analytiq_client()
    document = await ad.common.get_doc(analytiq_client, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get the OCR metadata from mongodb
    metadata = ad.common.get_ocr_metadata(analytiq_client, document_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="OCR metadata not found")
    
    return GetOCRMetadataResponse(
        n_pages=metadata["n_pages"],
        ocr_date=metadata["ocr_date"].isoformat()
    )

# LLM Run Endpoints
@app.post("/v0/orgs/{organization_id}/llm/run/{document_id}", response_model=LLMRunResponse, tags=["llm"])
async def run_llm_analysis(
    organization_id: str,
    document_id: str,
    prompt_id: str = Query(default="default", description="The prompt ID to use"),
    force: bool = Query(default=False, description="Force new run even if result exists"),
    current_user: User = Depends(get_current_user)
):
    """
    Run LLM on a document, with optional force refresh.
    """
    ad.log.debug(f"run_llm_analysis() start: document_id: {document_id}, prompt_id: {prompt_id}, force: {force}")
    analytiq_client = ad.common.get_analytiq_client()
    
    # Verify document exists and user has access
    document = await ad.common.get_doc(analytiq_client, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify OCR is complete
    ocr_metadata = ad.common.get_ocr_metadata(analytiq_client, document_id)
    if ocr_metadata is None:
        raise HTTPException(status_code=404, detail="OCR metadata not found")

    try:
        result = await ad.llm.run_llm(
            analytiq_client,
            document_id=document_id,
            prompt_id=prompt_id,
            force=force
        )
        
        return LLMRunResponse(
            status="success",
            result=result
        )
        
    except Exception as e:
        ad.log.error(f"Error in LLM run: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}"
        )

@app.get("/v0/orgs/{organization_id}/llm/result/{document_id}", response_model=LLMResult, tags=["llm"])
async def get_llm_result(
    organization_id: str,
    document_id: str,
    prompt_id: str = Query(default="default", description="The prompt ID to retrieve"),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve existing LLM results for a document.
    """
    ad.log.debug(f"get_llm_result() start: document_id: {document_id}, prompt_id: {prompt_id}")
    analytiq_client = ad.common.get_analytiq_client()
    
    # Verify document exists and user has access
    document = await ad.common.get_doc(analytiq_client, document_id, organization_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    llm_result = await ad.llm.get_llm_result(analytiq_client, document_id, prompt_id)
    if not llm_result:
        raise HTTPException(
            status_code=404,
            detail=f"LLM result not found for document_id: {document_id} and prompt_id: {prompt_id}"
        )
    
    return llm_result

@app.put("/v0/orgs/{organization_id}/llm/result/{document_id}", response_model=LLMResult, tags=["llm"])
async def update_llm_result(
    organization_id: str,
    document_id: str,
    prompt_id: str = Query(..., description="The prompt ID to update"),
    update: UpdateLLMResultRequest = Body(..., description="The update request"),
    current_user: User = Depends(get_current_user)
):
    """
    Update LLM results with user edits and verification status.
    """
    analytiq_client = ad.common.get_analytiq_client()
    
    # Verify document exists and user has access
    document = await ad.common.get_doc(analytiq_client, document_id, organization_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        await ad.llm.update_llm_result(
            analytiq_client,
            document_id=document_id,
            prompt_id=prompt_id,
            updated_llm_result=update.updated_llm_result,
            is_verified=update.is_verified
        )
        
        return await ad.llm.get_llm_result(analytiq_client, document_id, prompt_id)
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating LLM result: {str(e)}"
        )

@app.delete("/v0/orgs/{organization_id}/llm/result/{document_id}", tags=["llm"])
async def delete_llm_result(
    organization_id: str,
    document_id: str,
    prompt_id: str = Query(..., description="The prompt ID to delete"),
    current_user: User = Depends(get_current_user)
):
    """
    Delete LLM results for a specific document and prompt.
    """
    ad.log.debug(f"delete_llm_result() start: document_id: {document_id}, prompt_id: {prompt_id}")
    analytiq_client = ad.common.get_analytiq_client()
    # Verify document exists and user has access
    document = await ad.common.get_doc(analytiq_client, document_id, organization_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    deleted = await ad.llm.delete_llm_result(analytiq_client, document_id, prompt_id)
    
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"LLM result not found for document_id: {document_id} and prompt_id: {prompt_id}"
        )
    
    return {"status": "success", "message": "LLM result deleted"}

# Add this helper function near the top of the file with other functions
async def get_next_schema_version(schema_id: str) -> int:
    """Atomically get the next version number for a schema"""
    db = ad.common.get_async_db()
    result = await db.schema_versions.find_one_and_update(
        {"_id": schema_id},
        {"$inc": {"version": 1}},
        upsert=True,
        return_document=True
    )
    return result["version"]

# Schema management endpoints
@app.post("/v0/orgs/{organization_id}/schemas", response_model=Schema, tags=["schemas"])
async def create_schema(
    organization_id: str,
    schema: SchemaConfig,
    current_user: User = Depends(get_current_user)
):
    """Create a schema"""
    db = ad.common.get_async_db()

    # Check if schema with this name already exists (case-insensitive)
    existing_schema = await db.schemas.find_one({
        "name": {"$regex": f"^{schema.name}$", "$options": "i"},
        "organization_id": organization_id
    })

    # Create or use existing schema_id
    if existing_schema and "schema_id" in existing_schema:
        schema_id = existing_schema["schema_id"]
    else:
        schema_id = schema.name.lower().replace(" ", "_")
    
    # Get the next version
    new_version = await get_next_schema_version(schema_id)
    
    # Create schema document
    schema_dict = {
        "name": existing_schema["name"] if existing_schema else schema.name,
        "schema_id": schema_id,
        "response_format": schema.response_format.model_dump(),
        "version": new_version,
        "created_at": datetime.now(UTC),
        "created_by": current_user.user_id,
        "organization_id": organization_id,
    }
    
    # Insert into MongoDB
    result = await db.schemas.insert_one(schema_dict)
    
    # Return complete schema
    schema_dict["id"] = str(result.inserted_id)
    return Schema(**schema_dict)

@app.get("/v0/orgs/{organization_id}/schemas", response_model=ListSchemasResponse, tags=["schemas"])
async def list_schemas(
    organization_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """List schemas within an organization"""
    db = ad.common.get_async_db()
    # Build the base pipeline with organization filter
    pipeline = [
        {
            "$match": {
                "organization_id": organization_id,
            }
        },
        {
            "$sort": {"_id": -1}
        },
        {
            "$group": {
                "_id": "$schema_id",  # Group by schema_id instead of name
                "doc": {"$first": "$$ROOT"}
            }
        },
        {
            "$replaceRoot": {"newRoot": "$doc"}
        },
        {
            "$sort": {"_id": -1}
        },
        {
            "$facet": {
                "total": [{"$count": "count"}],
                "schemas": [
                    {"$skip": skip},
                    {"$limit": limit}
                ]
            }
        }
    ]
    
    result = await db.schemas.aggregate(pipeline).to_list(length=1)
    result = result[0]
    
    total_count = result["total"][0]["count"] if result["total"] else 0
    schemas = result["schemas"]
    
    # Convert _id to id in each schema
    for schema in schemas:
        schema['id'] = str(schema.pop('_id'))
    
    return ListSchemasResponse(
        schemas=schemas,
        total_count=total_count,
        skip=skip
    )

@app.get("/v0/orgs/{organization_id}/schemas/{schema_id}", response_model=Schema, tags=["schemas"])
async def get_schema(
    organization_id: str,
    schema_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a schema"""
    db = ad.common.get_async_db()
    schema = await db.schemas.find_one({
        "_id": ObjectId(schema_id),
        "organization_id": organization_id,
    })
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    schema['id'] = str(schema.pop('_id'))
    return Schema(**schema)

@app.put("/v0/orgs/{organization_id}/schemas/{schema_id}", response_model=Schema, tags=["schemas"])
async def update_schema(
    organization_id: str,
    schema_id: str,
    schema: SchemaConfig,
    current_user: User = Depends(get_current_user)
):
    """Update a schema"""
    ad.log.info(f"update_schema() start: organization_id: {organization_id}, schema_id: {schema_id}, schema: {schema}")
    
    db = ad.common.get_async_db()
    # Get the existing schema with organization check
    existing_schema = await db.schemas.find_one({
        "_id": ObjectId(schema_id),
        "organization_id": organization_id,
    })
    if not existing_schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    # Check if user has permission to update
    if existing_schema["created_by"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this schema")
    
    # Check if only the name has changed
    only_name_changed = (
        schema.name != existing_schema["name"] and
        schema.response_format.model_dump() == existing_schema["response_format"]
    )
    
    if only_name_changed:
        # Update the name without creating a new version
        result = await db.schemas.update_one(
            {"_id": ObjectId(schema_id)},
            {"$set": {"name": schema.name}}
        )
        
        if result.modified_count > 0:
            # Return the updated schema
            updated_schema = await db.schemas.find_one({"_id": ObjectId(schema_id)})
            updated_schema["id"] = str(updated_schema.pop("_id"))
            return Schema(**updated_schema)
        else:
            raise HTTPException(status_code=500, detail="Failed to update schema name")
    
    # If other fields changed, create a new version
    # Atomically get the next version number using the stable schema_id
    new_version = await get_next_schema_version(existing_schema["schema_id"])
    
    # Create new version of the schema
    new_schema = {
        "name": schema.name,
        "schema_id": existing_schema["schema_id"],  # Preserve stable identifier
        "response_format": schema.response_format.model_dump(),
        "version": new_version,
        "created_at": datetime.now(UTC),
        "created_by": current_user.user_id,
        "organization_id": organization_id,
    }
    
    # Insert new version
    result = await db.schemas.insert_one(new_schema)
    
    # Return updated schema
    new_schema["id"] = str(result.inserted_id)
    return Schema(**new_schema)

@app.delete("/v0/orgs/{organization_id}/schemas/{schema_id}", tags=["schemas"])
async def delete_schema(
    organization_id: str,
    schema_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a schema"""
    db = ad.common.get_async_db()
    
    # Get the schema first to check permissions
    schema = await db.schemas.find_one({
        "_id": ObjectId(schema_id),
        "organization_id": organization_id,
    })
    
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
        
    # Check if user has permission to delete
    if schema["created_by"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this schema")
    
    # Check for dependent prompts by schema_id instead of schema_name
    dependent_prompts = await db.prompts.find({
        "schema_id": schema["schema_id"],
        "organization_id": organization_id
    }).to_list(None)
    
    if dependent_prompts:
        # Format the list of dependent prompts
        prompt_list = [
            {"name": p["name"], "version": p["version"]} 
            for p in dependent_prompts
        ]
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete schema because it has dependent prompts:{json.dumps(prompt_list)}"
        )
    
    # If no dependent prompts, proceed with deletion
    result = await db.schemas.delete_many({
        "schema_id": schema["schema_id"],
        "organization_id": organization_id
    })
    
    # Also delete the version counter
    await db.schema_versions.delete_one({"_id": schema["schema_id"]})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Schema not found")
        
    return {"message": "Schema deleted successfully"}

@app.post("/v0/orgs/{organization_id}/schemas/{schema_id}/validate", tags=["schemas"])
async def validate_against_schema(
    organization_id: str,
    schema_id: str,
    data: dict = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Validate data against a schema"""
    ad.log.info(f"validate_against_schema() start: organization_id: {organization_id}, schema_id: {schema_id}")
    
    db = ad.common.get_async_db()
    
    # Get the schema
    schema_doc = await db.schemas.find_one({
        "_id": ObjectId(schema_id),
        "organization_id": organization_id
    })
    
    if not schema_doc:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    # Extract the JSON schema from the schema document
    try:
        json_schema = schema_doc["response_format"]["json_schema"]["schema"]
        
        # Get the data to validate
        if "data" not in data:
            raise HTTPException(status_code=400, detail="Request must include 'data' field")
        
        instance_data = data["data"]
        
        # Validate the data against the schema
        validator = Draft7Validator(json_schema)
        errors = list(validator.iter_errors(instance_data))
        
        if not errors:
            return {"valid": True}
        
        # Format validation errors
        formatted_errors = []
        for error in errors:
            formatted_errors.append({
                "path": ".".join(str(p) for p in error.path) if error.path else "",
                "message": error.message
            })
        
        return {
            "valid": False,
            "errors": formatted_errors
        }
    
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Invalid schema format: {str(e)}")
    except Exception as e:
        ad.log.error(f"Error validating data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error validating data: {str(e)}")


# Add this validation function
def validate_schema_fields(fields: list) -> tuple[bool, str]:
    field_names = [field.name.lower() for field in fields]
    seen = set()
    for name in field_names:
        if name in seen:
            return False, f"Duplicate field name: {name}"
        seen.add(name)
    return True, ""

# Add this helper function near get_next_schema_version
async def get_next_prompt_version(prompt_id: str) -> int:
    """Atomically get the next version number for a prompt"""
    db = ad.common.get_async_db()
    result = await db.prompt_versions.find_one_and_update(
        {"_id": prompt_id},
        {"$inc": {"version": 1}},
        upsert=True,
        return_document=True
    )
    return result["version"]

# Prompt management endpoints
@app.post("/v0/orgs/{organization_id}/prompts", response_model=Prompt, tags=["prompts"])
async def create_prompt(
    organization_id: str,
    prompt: PromptConfig,
    current_user: User = Depends(get_current_user)
):
    """Create a prompt"""
    db = ad.common.get_async_db()
    
    # Verify schema if specified
    if prompt.schema_id and prompt.schema_version:
        schema = await db.schemas.find_one({
            "schema_id": prompt.schema_id,
            "version": prompt.schema_version,
            "organization_id": organization_id
        })
        if not schema:
            raise HTTPException(
                status_code=404,
                detail=f"Schema with ID {prompt.schema_id} version {prompt.schema_version} not found"
            )

    # Validate model exists
    model = await db.llm_models.find_one({"name": prompt.model})
    if not model:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model: {prompt.model}"
        )

    # Validate tag IDs if provided
    if prompt.tag_ids:
        tags_cursor = db.tags.find({
            "_id": {"$in": [ObjectId(tag_id) for tag_id in prompt.tag_ids]},
            "organization_id": organization_id
        })
        existing_tags = await tags_cursor.to_list(None)
        existing_tag_ids = {str(tag["_id"]) for tag in existing_tags}
        
        invalid_tags = set(prompt.tag_ids) - existing_tag_ids
        if invalid_tags:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tag IDs: {list(invalid_tags)}"
            )
        # Only set schema_id if schema exists and was verified above
        if prompt.schema_id and 'schema' in locals():
            prompt.schema_id = schema["schema_id"]

    # Create a stable identifier for the prompt. TODO: This should be a UUID
    prompt_id = prompt.name.lower().replace(" ", "_")
    
    # Get the next version - modify to use prompt_id instead of name
    new_version = await get_next_prompt_version(prompt_id)
    
    # Create prompt document
    prompt_dict = {
        "name": prompt.name,
        "prompt_id": prompt_id,  # Add stable identifier
        "content": prompt.content,
        "schema_id": prompt.schema_id,
        "schema_name": prompt.schema_name,
        "schema_version": prompt.schema_version,
        "version": new_version,
        "created_at": datetime.now(UTC),
        "created_by": current_user.user_id,
        "tag_ids": prompt.tag_ids,
        "model": prompt.model,
        "organization_id": organization_id
    }
    
    # Insert into MongoDB
    result = await db.prompts.insert_one(prompt_dict)
    
    # Return complete prompt
    prompt_dict["id"] = str(result.inserted_id)
    return Prompt(**prompt_dict)

@app.get("/v0/orgs/{organization_id}/prompts", response_model=ListPromptsResponse, tags=["prompts"])
async def list_prompts(
    organization_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    document_id: str = Query(None, description="Filter prompts by document's tags"),
    tag_ids: str = Query(None, description="Comma-separated list of tag IDs"),
    current_user: User = Depends(get_current_user)
):
    """List prompts within an organization"""
    db = ad.common.get_async_db()
    # Build the base pipeline
    pipeline = [
        {
            "$match": {"organization_id": organization_id}
        }
    ]

    # Add document tag filtering if document_id is provided
    if document_id:
        document = await db.docs.find_one({
            "_id": ObjectId(document_id),
            "organization_id": organization_id  # Ensure document belongs to org
        })
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document_tag_ids = document.get("tag_ids", [])
        if document_tag_ids:
            pipeline.append({
                "$match": {"tag_ids": {"$in": document_tag_ids}}
            })
    # Add direct tag filtering if tag_ids are provided
    elif tag_ids:
        tag_id_list = [tid.strip() for tid in tag_ids.split(",")]
        pipeline.append({
            "$match": {"tag_ids": {"$all": tag_id_list}}
        })
    
    # Add the rest of the pipeline stages
    pipeline.extend([
        {
            "$sort": {"_id": -1}
        },
        {
            "$group": {
                "_id": "$prompt_id",  # Group by prompt_id instead of name
                "doc": {"$first": "$$ROOT"}
            }
        },
        {
            "$replaceRoot": {"newRoot": "$doc"}
        },
        {
            "$sort": {"_id": -1}
        },
        {
            "$facet": {
                "total": [{"$count": "count"}],
                "prompts": [
                    {"$skip": skip},
                    {"$limit": limit}
                ]
            }
        }
    ])
    
    result = await db.prompts.aggregate(pipeline).to_list(length=1)
    result = result[0]
    
    total_count = result["total"][0]["count"] if result["total"] else 0
    prompts = result["prompts"]
    
    # Convert _id to id in each prompt
    for prompt in prompts:
        prompt['id'] = str(prompt.pop('_id'))
    
    return ListPromptsResponse(
        prompts=prompts,
        total_count=total_count,
        skip=skip
    )

@app.get("/v0/orgs/{organization_id}/prompts/{prompt_id}", response_model=Prompt, tags=["prompts"])
async def get_prompt(
    organization_id: str,
    prompt_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a prompt"""
    db = ad.common.get_async_db()
    prompt = await db.prompts.find_one({
        "_id": ObjectId(prompt_id),
        "organization_id": organization_id  # Add organization check
    })
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    prompt['id'] = str(prompt.pop('_id'))
    return Prompt(**prompt)

@app.put("/v0/orgs/{organization_id}/prompts/{prompt_id}", response_model=Prompt, tags=["prompts"])
async def update_prompt(
    organization_id: str,
    prompt_id: str,
    prompt: PromptConfig,
    current_user: User = Depends(get_current_user)
):
    """Update a prompt"""
    db = ad.common.get_async_db()
    # Get the existing prompt with organization check
    existing_prompt = await db.prompts.find_one({
        "_id": ObjectId(prompt_id),
        "organization_id": organization_id
    })
    if not existing_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # Only verify schema if one is specified
    if prompt.schema_name and prompt.schema_version:
        schema = await db.schemas.find_one({
            "name": prompt.schema_name,
            "version": prompt.schema_version
        })
        if not schema:
            raise HTTPException(
                status_code=404,
                detail=f"Schema {prompt.schema_name} version {prompt.schema_version} not found"
            )

    # Validate model exists
    model = await db.llm_models.find_one({"name": prompt.model})
    if not model:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model: {prompt.model}"
        )
    
    # Validate tag IDs if provided
    if prompt.tag_ids:
        tags_cursor = db.tags.find({
            "_id": {"$in": [ObjectId(tag_id) for tag_id in prompt.tag_ids]},
            "organization_id": organization_id
        })
        existing_tags = await tags_cursor.to_list(None)
        existing_tag_ids = {str(tag["_id"]) for tag in existing_tags}
        
        invalid_tags = set(prompt.tag_ids) - existing_tag_ids
        if invalid_tags:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tag IDs: {list(invalid_tags)}"
            )
    
    # Handle schema references (similar to create_prompt)
    if prompt.schema_id and prompt.schema_version:
        schema = await db.schemas.find_one({
            "schema_id": prompt.schema_id,
            "version": prompt.schema_version
        })
        if not schema:
            raise HTTPException(
                status_code=404,
                detail=f"Schema with ID {prompt.schema_id} version {prompt.schema_version} not found"
            )
        prompt.schema_name = schema["name"]
    
    
    # Check if only the name has changed
    only_name_changed = (
        prompt.name != existing_prompt["name"] and
        prompt.content == existing_prompt["content"] and
        prompt.schema_id == existing_prompt.get("schema_id") and
        prompt.schema_version == existing_prompt.get("schema_version") and
        prompt.model == existing_prompt["model"] and
        set(prompt.tag_ids or []) == set(existing_prompt.get("tag_ids") or [])
    )
    
    if only_name_changed:
        # Update the name without creating a new version
        result = await db.prompts.update_one(
            {"_id": ObjectId(prompt_id)},
            {"$set": {"name": prompt.name}}
        )
        
        if result.modified_count > 0:
            # Return the updated prompt
            updated_prompt = await db.prompts.find_one({"_id": ObjectId(prompt_id)})
            updated_prompt["id"] = str(updated_prompt.pop("_id"))
            return Prompt(**updated_prompt)
        else:
            raise HTTPException(status_code=500, detail="Failed to update prompt name")
    
    # If other fields changed, create a new version
    # Get the next version number using the stable prompt_id
    new_version = await get_next_prompt_version(existing_prompt["prompt_id"])
    
    # Create new version of the prompt
    new_prompt = {
        "name": prompt.name,
        "prompt_id": existing_prompt["prompt_id"],  # Preserve stable identifier
        "content": prompt.content,
        "schema_id": prompt.schema_id,
        "schema_name": prompt.schema_name,
        "schema_version": prompt.schema_version,
        "version": new_version,
        "created_at": datetime.now(UTC),
        "created_by": current_user.user_id,
        "tag_ids": prompt.tag_ids,
        "model": prompt.model,
        "organization_id": organization_id
    }
    
    # Insert new version
    result = await db.prompts.insert_one(new_prompt)
    
    # Return updated prompt
    new_prompt["id"] = str(result.inserted_id)
    return Prompt(**new_prompt)

@app.delete("/v0/orgs/{organization_id}/prompts/{prompt_id}", tags=["prompts"])
async def delete_prompt(
    organization_id: str,
    prompt_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a prompt"""
    db = ad.common.get_async_db()
    # Get the prompt to find its name
    prompt = await db.prompts.find_one({
        "_id": ObjectId(prompt_id),
        "organization_id": organization_id  # Add organization check
    })
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    if prompt["created_by"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this prompt")
    
    # Delete all versions of this prompt within the organization
    result = await db.prompts.delete_many({
        "prompt_id": prompt["prompt_id"],
        "organization_id": organization_id  # Add organization check
    })
    
    # Also delete the version counter
    await db.prompt_versions.delete_one({"_id": prompt["prompt_id"]})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"message": "Prompt deleted successfully"}

# Tag management endpoints
@app.post("/v0/orgs/{organization_id}/tags", response_model=Tag, tags=["tags"])
async def create_tag(
    organization_id: str,
    tag: TagConfig,
    current_user: User = Depends(get_current_user)
):
    """Create a tag"""
    db = ad.common.get_async_db()
    # Check if tag with this name already exists for this user
    existing_tag = await db.tags.find_one({
        "name": tag.name,
        "organization_id": organization_id
    })
    
    if existing_tag:
        raise HTTPException(
            status_code=400,
            detail=f"Tag with name '{tag.name}' already exists"
        )

    new_tag = {
        "name": tag.name,
        "color": tag.color,
        "description": tag.description,
        "created_at": datetime.now(UTC),
        "created_by": current_user.user_id,
        "organization_id": organization_id  # Add organization_id
    }
    
    result = await db.tags.insert_one(new_tag)
    new_tag["id"] = str(result.inserted_id)
    
    return Tag(**new_tag)

@app.get("/v0/orgs/{organization_id}/tags", response_model=ListTagsResponse, tags=["tags"])
async def list_tags(
    organization_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """List tags"""
    db = ad.common.get_async_db()
    # Get total count
    total_count = await db.tags.count_documents({"organization_id": organization_id})
    
    # Get paginated tags with sorting by _id in descending order
    cursor = db.tags.find(
        {"organization_id": organization_id}
    ).sort("_id", -1).skip(skip).limit(limit)  # Sort by _id descending (newest first)
    
    tags = await cursor.to_list(length=None)
    
    return ListTagsResponse(
        tags=[
            {
                "id": str(tag["_id"]),
                "name": tag["name"],
                "color": tag.get("color"),
                "description": tag.get("description"),
                "created_at": tag["created_at"],
                "created_by": tag["created_by"]
            }
            for tag in tags
        ],
        total_count=total_count,
        skip=skip
    )

@app.delete("/v0/orgs/{organization_id}/tags/{tag_id}", tags=["tags"])
async def delete_tag(
    organization_id: str,
    tag_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a tag"""
    db = ad.common.get_async_db()
    # Verify tag exists and belongs to user
    tag = await db.tags.find_one({
        "_id": ObjectId(tag_id),
        "organization_id": organization_id
    })
    
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    # Check if tag is used in any documents
    documents_with_tag = await db.docs.find_one({
        "tag_ids": tag_id
    })
    
    if documents_with_tag:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete tag '{tag['name']}' because it is assigned to one or more documents"
        )

    # Check if tag is used in any prompts
    prompts_with_tag = await db.prompts.find_one({
        "tag_ids": tag_id
    })
    
    if prompts_with_tag:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete tag '{tag['name']}' because it is assigned to one or more prompts"
        )
    
    result = await db.tags.delete_one({
        "_id": ObjectId(tag_id),
        "organization_id": organization_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    return {"message": "Tag deleted successfully"}

@app.put("/v0/orgs/{organization_id}/tags/{tag_id}", response_model=Tag, tags=["tags"])
async def update_tag(
    organization_id: str,
    tag_id: str,
    tag: TagConfig,
    current_user: User = Depends(get_current_user)
):
    """Update a tag"""
    db = ad.common.get_async_db()
    
    # Verify tag exists and belongs to user
    existing_tag = await db.tags.find_one({
        "_id": ObjectId(tag_id),
        "organization_id": organization_id
    })
    
    if not existing_tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    # Update all fields including name
    update_data = {
        "name": tag.name,
        "color": tag.color,
        "description": tag.description
    }
    
    updated_tag = await db.tags.find_one_and_update(
        {"_id": ObjectId(tag_id)},
        {"$set": update_data},
        return_document=True
    )
    
    if not updated_tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    return Tag(**{**updated_tag, "id": str(updated_tag["_id"])})

@app.post("/v0/orgs/{organization_id}/flows", tags=["flows"])
async def create_flow(
    organization_id: str,
    flow: FlowConfig,
    current_user: User = Depends(get_current_user)
) -> Flow:
    db = ad.common.get_async_db()
    try:
        # Validate tag IDs if provided
        if flow.tag_ids:
            tags_cursor = db.tags.find({
                "_id": {"$in": [ObjectId(tag_id) for tag_id in flow.tag_ids]},
                "organization_id": organization_id
            })
            existing_tags = await tags_cursor.to_list(None)
            existing_tag_ids = {str(tag["_id"]) for tag in existing_tags}
            
            invalid_tags = set(flow.tag_ids) - existing_tag_ids
            if invalid_tags:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid tag IDs: {list(invalid_tags)}"
                )

        flow_id = ad.common.create_id()
        flow_data = {
            "_id": ObjectId(flow_id),
            "name": flow.name,
            "description": flow.description,
            "nodes": jsonable_encoder(flow.nodes),
            "edges": jsonable_encoder(flow.edges),
            "tag_ids": flow.tag_ids,
            "version": 1,
            "created_at": datetime.now(UTC),
            "created_by": current_user.user_name,
            "organization_id": organization_id  # Add organization_id
        }
        
        # Save to MongoDB
        await db.flows.insert_one(flow_data)
        
        # Convert _id to string for response
        flow_data["id"] = str(flow_data.pop("_id"))
        return Flow(**flow_data)
        
    except Exception as e:
        ad.log.error(f"Error creating flow: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating flow: {str(e)}"
        )

@app.get("/v0/orgs/{organization_id}/flows", tags=["flows"])
async def list_flows(
    organization_id: str,
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user)
) -> ListFlowsResponse:
    db = ad.common.get_async_db()
    cursor = db.flows.find({
        "created_by": current_user.user_name,
        "organization_id": organization_id  # Add organization filter
    }).skip(skip).limit(limit)
    
    flows = await cursor.to_list(None)
    
    total_count = await db.flows.count_documents({
        "created_by": current_user.user_name,
        "organization_id": organization_id  # Add organization filter
    })
    
    # Convert MongoDB documents to Flow models
    flow_list = []
    for flow in flows:
        flow_dict = {
            "id": str(flow["_id"]),
            "name": flow["name"],
            "description": flow.get("description"),
            "nodes": flow["nodes"],
            "edges": flow["edges"],
            "tag_ids": flow.get("tag_ids", []),
            "version": flow.get("version", 1),
            "created_at": flow["created_at"],
            "created_by": flow["created_by"]
        }
        flow_list.append(FlowMetadata(**flow_dict))
    
    return ListFlowsResponse(
        flows=flow_list,
        total_count=total_count,
        skip=skip
    )

@app.get("/v0/orgs/{organization_id}/flows/{flow_id}", tags=["flows"])
async def get_flow(
    organization_id: str,
    flow_id: str,
    current_user: User = Depends(get_current_user)
) -> Flow:
    db = ad.common.get_async_db()
    try:
        # Find the flow in MongoDB with organization check
        flow = await db.flows.find_one({
            "_id": ObjectId(flow_id),
            "organization_id": organization_id,
            "created_by": current_user.user_name
        })
        
        if not flow:
            raise HTTPException(
                status_code=404,
                detail=f"Flow with id {flow_id} not found"
            )
        
        # Convert MongoDB _id to string id for response
        flow_dict = {
            "id": str(flow["_id"]),
            "name": flow["name"],
            "description": flow.get("description"),
            "nodes": flow["nodes"],
            "edges": flow["edges"],
            "tag_ids": flow.get("tag_ids", []),
            "version": flow.get("version", 1),
            "created_at": flow["created_at"],
            "created_by": flow["created_by"]
        }
        
        return Flow(**flow_dict)
        
    except Exception as e:
        ad.log.error(f"Error getting flow {flow_id}: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Error getting flow: {str(e)}"
        )

@app.delete("/v0/orgs/{organization_id}/flows/{flow_id}", tags=["flows"])
async def delete_flow(
    organization_id: str,
    flow_id: str,
    current_user: User = Depends(get_current_user)
) -> dict:
    db = ad.common.get_async_db()
    try:
        # Find and delete the flow, ensuring user can only delete their own flows within the organization
        result = await db.flows.delete_one({
            "_id": ObjectId(flow_id),
            "created_by": current_user.user_name,
            "organization_id": organization_id  # Add organization check
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Flow with id {flow_id} not found"
            )
        
        return {"message": "Flow deleted successfully"}
        
    except Exception as e:
        ad.log.error(f"Error deleting flow {flow_id}: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting flow: {str(e)}"
        )

@app.put("/v0/orgs/{organization_id}/flows/{flow_id}", tags=["flows"])
async def update_flow(
    organization_id: str,
    flow_id: str,
    flow: FlowConfig,
    current_user: User = Depends(get_current_user)
) -> Flow:
    db = ad.common.get_async_db()
    try:
        # Find the flow and verify ownership with organization check
        existing_flow = await db.flows.find_one({
            "_id": ObjectId(flow_id),
            "organization_id": organization_id,
            "created_by": current_user.user_name
        })
        
        if not existing_flow:
            raise HTTPException(
                status_code=404,
                detail=f"Flow with id {flow_id} not found"
            )
        
        # Prepare update data
        update_data = {
            "name": flow.name,
            "description": flow.description,
            "nodes": jsonable_encoder(flow.nodes),
            "edges": jsonable_encoder(flow.edges),
            "tag_ids": flow.tag_ids,
            "version": existing_flow.get("version", 1) + 1,
            "updated_at": datetime.now(UTC)
        }
        
        # Update the flow
        result = await db.flows.find_one_and_update(
            {
                "_id": ObjectId(flow_id),
                "created_by": current_user.user_name
            },
            {"$set": update_data},
            return_document=True
        )
        
        return Flow(**{
            "id": str(result["_id"]),
            "name": result["name"],
            "description": result.get("description"),
            "nodes": result["nodes"],
            "edges": result["edges"],
            "tag_ids": result.get("tag_ids", []),
            "version": result["version"],
            "created_at": result["created_at"],
            "created_by": result["created_by"]
        })
        
    except Exception as e:
        ad.log.error(f"Error updating flow {flow_id}: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Error updating flow: {str(e)}"
        )

@app.post("/v0/account/auth/token", tags=["account/auth"])
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

async def get_current_org(
    current_user: User = Depends(get_current_user),
    organization_id: Optional[str] = None
) -> Optional[str]:
    """
    Get the current organization ID if valid for the user.
    Returns None for account-level access.
    Raises HTTPException if organization_id is provided but invalid.
    """
    if not organization_id:
        return None
        
    db = ad.common.get_async_db()
    
    # Check if user is member of the organization
    org = await db.organizations.find_one({
        "_id": ObjectId(organization_id),
        "members": {
            "$elemMatch": {
                "user_id": current_user.user_id
            }
        }
    })
    
    if not org:
        raise HTTPException(
            status_code=403,
            detail="User is not a member of this organization"
        )
    
    return organization_id

# Update the access token endpoints to use organization context
@app.post("/v0/account/access_tokens", response_model=AccessToken, tags=["account/access_tokens"])
async def access_token_create(
    request: CreateAccessTokenRequest,
    current_user: User = Depends(get_current_user),
    organization_id: Optional[str] = Depends(get_current_org)
):
    """Create an API token"""
    ad.log.debug(f"Creating API token for user: {current_user} request: {request}")
    db = ad.common.get_async_db()

    token = secrets.token_urlsafe(32)
    new_token = {
        "user_id": current_user.user_id,
        "organization_id": organization_id,  # This will be None for account-level tokens
        "name": request.name,
        "token": ad.crypto.encrypt_token(token),
        "created_at": datetime.now(UTC),
        "lifetime": request.lifetime
    }
    result = await db.access_tokens.insert_one(new_token)

    # Return the new token with the id
    new_token["token"] = token  # Return plaintext token to user
    new_token["id"] = str(result.inserted_id)
    return new_token

@app.get("/v0/account/access_tokens", response_model=ListAccessTokensResponse, tags=["account/access_tokens"])
async def access_token_list(
    current_user: User = Depends(get_current_user),
    organization_id: Optional[str] = Depends(get_current_org)
):
    """List API tokens"""
    db = ad.common.get_async_db()
    
    # Build query for either org-specific or account-level tokens
    query = {
        "user_id": current_user.user_id,
    }
    if organization_id:
        query["organization_id"] = organization_id
    else:
        # For account-level listing, only show tokens without organization_id
        query["organization_id"] = None
        
    cursor = db.access_tokens.find(query)
    tokens = await cursor.to_list(length=None)
    ret = [
        {
            "id": str(token["_id"]),
            "user_id": token["user_id"],
            "organization_id": token.get("organization_id"),
            "name": token["name"],
            "token": token["token"],
            "created_at": token["created_at"],
            "lifetime": token["lifetime"]
        }
        for token in tokens
    ]
    return ListAccessTokensResponse(access_tokens=ret)

@app.delete("/v0/account/access_tokens/{token_id}", tags=["account/access_tokens"])
async def access_token_delete(
    token_id: str,
    current_user: User = Depends(get_current_user),
    organization_id: Optional[str] = Depends(get_current_org)
):
    """Delete an API token"""
    db = ad.common.get_async_db()
    
    # Build query to ensure user can only delete their own tokens
    query = {
        "_id": ObjectId(token_id),
        "user_id": current_user.user_id,
    }
    if organization_id:
        query["organization_id"] = organization_id
    else:
        query["organization_id"] = None
        
    result = await db.access_tokens.delete_one(query)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token deleted successfully"}

@app.get("/v0/account/llm_models", response_model=ListLLMModelsResponse, tags=["account/llm_models"])
async def list_llm_models():
    """List all supported LLM models"""
    db = ad.common.get_async_db()
    
    # Retrieve models from MongoDB
    cursor = db.llm_models.find({})
    models = await cursor.to_list(length=None)
    
    # Convert MongoDB documents to LLMModel instances
    llm_models = []
    for model in models:
        ad.log.info(f"model: {model}")
        llm_models.append(LLMModel(
            id=str(model["_id"]),
            name=model["name"],
            provider=model["provider"],
            description=model["description"],
            max_tokens=model["max_tokens"],
            cost_per_1m_input_tokens=model["cost_per_1m_input_tokens"],
            cost_per_1m_output_tokens=model["cost_per_1m_output_tokens"]
        ))
    
    return ListLLMModelsResponse(models=llm_models)

@app.post("/v0/account/llm_tokens", response_model=LLMToken, tags=["account/llm_tokens"])
async def llm_token_create(
    request: CreateLLMTokenRequest,
    current_user: User = Depends(get_admin_user)
):
    """Create or update an LLM token (admin only)"""
    ad.log.debug(f"Creating/Updating LLM token for user: {current_user} request: {request}")
    db = ad.common.get_async_db()

    # Check if a token for this vendor already exists
    existing_token = await db.llm_tokens.find_one({
        "user_id": current_user.user_id,
        "llm_vendor": request.llm_vendor
    })

    new_token = {
        "user_id": current_user.user_id,
        "llm_vendor": request.llm_vendor,
        "token": ad.crypto.encrypt_token(request.token),
        "created_at": datetime.now(UTC),
    }

    if existing_token:
        # Update the existing token
        result = await db.llm_tokens.replace_one(
            {"_id": existing_token["_id"]},
            new_token
        )
        new_token["id"] = str(existing_token["_id"])
        ad.log.debug(f"Updated existing LLM token for {request.llm_vendor}")
    else:
        # Insert a new token
        result = await db.llm_tokens.insert_one(new_token)
        new_token["id"] = str(result.inserted_id)
        new_token["token"] = ad.crypto.decrypt_token(new_token["token"])
        ad.log.debug(f"Created new LLM token for {request.llm_vendor}")

    return new_token

@app.get("/v0/account/llm_tokens", response_model=ListLLMTokensResponse, tags=["account/llm_tokens"])
async def llm_token_list(current_user: User = Depends(get_admin_user)):
    """List LLM tokens (admin only)"""
    db = ad.common.get_async_db()
    cursor = db.llm_tokens.find({"user_id": current_user.user_id})
    tokens = await cursor.to_list(length=None)
    llm_tokens = [
        {
            "id": str(token["_id"]),
            "user_id": token["user_id"],
            "llm_vendor": token["llm_vendor"],
            "token": ad.crypto.decrypt_token(token["token"]),
            "created_at": token["created_at"],
        }
        for token in tokens
    ]
    return ListLLMTokensResponse(llm_tokens=llm_tokens)

@app.delete("/v0/account/llm_tokens/{token_id}", tags=["account/llm_tokens"])
async def llm_token_delete(
    token_id: str,
    current_user: User = Depends(get_admin_user)
):
    """Delete an LLM token (admin only)"""
    db = ad.common.get_async_db()
    result = await db.llm_tokens.delete_one({
        "_id": ObjectId(token_id),
        "user_id": current_user.user_id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token deleted successfully"}

@app.post("/v0/account/aws_credentials", tags=["account/aws_credentials"])
async def create_aws_credentials(
    credentials: AWSCredentials,
    current_user: User = Depends(get_admin_user)
):  
    """Create or update AWS credentials (admin only)"""
    db = ad.common.get_async_db()
    # Validate AWS Access Key ID format
    if not re.match(r'^[A-Z0-9]{20}$', credentials.access_key_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid AWS Access Key ID format. Must be 20 characters long and contain only uppercase letters and numbers."
        )

    # Validate AWS Secret Access Key format
    if not re.match(r'^[A-Za-z0-9+/]{40}$', credentials.secret_access_key):
        raise HTTPException(
            status_code=400,
            detail="Invalid AWS Secret Access Key format. Must be 40 characters long and contain only letters, numbers, and +/."
        )

    encrypted_access_key = ad.crypto.encrypt_token(credentials.access_key_id)
    encrypted_secret_key = ad.crypto.encrypt_token(credentials.secret_access_key)
    
    await db.aws_credentials.update_one(
        {"user_id": current_user.user_id},
        {
            "$set": {
                "access_key_id": encrypted_access_key,
                "secret_access_key": encrypted_secret_key,
                "created_at": datetime.now(UTC)
            }
        },
        upsert=True
    )
    
    return {"message": "AWS credentials saved successfully"}

@app.get("/v0/account/aws_credentials", tags=["account/aws_credentials"])
async def get_aws_credentials(current_user: User = Depends(get_admin_user)):
    """Get AWS credentials (admin only)"""
    db = ad.common.get_async_db()
    credentials = await db.aws_credentials.find_one({"user_id": current_user.user_id})
    if not credentials:
        raise HTTPException(status_code=404, detail="AWS credentials not found")
        
    return {
        "access_key_id": ad.crypto.decrypt_token(credentials["access_key_id"]),
        "secret_access_key": ad.crypto.decrypt_token(credentials["secret_access_key"])
    }

@app.delete("/v0/account/aws_credentials", tags=["account/aws_credentials"])
async def delete_aws_credentials(current_user: User = Depends(get_admin_user)):
    """Delete AWS credentials (admin only)"""
    db = ad.common.get_async_db()
    result = await db.aws_credentials.delete_one({"user_id": current_user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="AWS credentials not found")
    return {"message": "AWS credentials deleted successfully"}

@app.get("/v0/account/organizations", response_model=ListOrganizationsResponse, tags=["account/organizations"])
async def list_organizations(
    user_id: str | None = Query(None, description="Filter organizations by user ID"),
    organization_id: str | None = Query(None, description="Get a specific organization by ID"),
    current_user: User = Depends(get_current_user)
):
    """
    List organizations or get a specific organization.
    - If organization_id is provided, returns just that organization
    - If user_id is provided, returns organizations for that user
    - Otherwise returns all organizations (admin only)
    - user_id and organization_id are mutually exclusive
    """
    ad.log.debug(f"list_organizations(): current_user: {current_user}")
    db = ad.common.get_async_db()
    ad.log.debug(f"list_organizations(): db: {db}")
    db_user = await db.users.find_one({"_id": ObjectId(current_user.user_id)})
    is_system_admin = db_user and db_user.get("role") == "admin"

    # user_id and organization_id are mutually exclusive
    if user_id and organization_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both user_id and organization_id"
        )

    # Handle single organization request
    if organization_id:
        try:
            organization = await db.organizations.find_one({"_id": ObjectId(organization_id)})
        except:
            raise HTTPException(status_code=404, detail="Organization not found")
            
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Check permissions
        is_org_admin = any(
            m["user_id"] == current_user.user_id and m["role"] == "admin" 
            for m in organization["members"]
        )

        if not (is_system_admin or is_org_admin):
            raise HTTPException(
                status_code=403,
                detail="Not authorized to view this organization"
            )

        return ListOrganizationsResponse(organizations=[
            Organization(**{
                **organization,
                "id": str(organization["_id"]),
                "type": organization["type"]
            })
        ])

    # Handle user filter
    if user_id:
        if not is_system_admin and user_id != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to view other users' organizations"
            )
        filter_user_id = user_id
    else:
        filter_user_id = None if is_system_admin else current_user.user_id

    # Build query for list request
    query = {}
    if filter_user_id:
        query["members.user_id"] = filter_user_id

    organizations = await db.organizations.find(query).to_list(None)

    return ListOrganizationsResponse(organizations=[
        Organization(**{
            **org,
            "id": str(org["_id"]),
            "type": org["type"]
        }) for org in organizations
    ])

@app.post("/v0/account/organizations", response_model=Organization, tags=["account/organizations"])
async def create_organization(
    organization: OrganizationCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new organization"""
    db = ad.common.get_async_db()

    # Check total organizations limit
    total_orgs = await db.organizations.count_documents({})
    if total_orgs >= limits.MAX_TOTAL_ORGANIZATIONS:
        raise HTTPException(
            status_code=403,
            detail="System limit reached: Maximum number of organizations exceeded"
        )

    # Check user's organization limit
    user_orgs = await db.organizations.count_documents({
        "members.user_id": current_user.user_id
    })
    if user_orgs >= limits.MAX_ORGANIZATIONS_PER_USER:
        raise HTTPException(
            status_code=403,
            detail=f"User limit reached: Cannot be member of more than {limits.MAX_ORGANIZATIONS_PER_USER} organizations"
        )

    # Check for existing organization with same name (case-insensitive)
    existing = await db.organizations.find_one({
        "name": {"$regex": f"^{organization.name}$", "$options": "i"}
    })
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"An organization named '{organization.name}' already exists"
        )

    # Create organization document
    org_doc = {
        "name": organization.name,
        "type": organization.type,
        "members": [{"user_id": current_user["user_id"], "role": "admin"}],
        "created_at": now,
        "updated_at": now,
        "mcp_enabled": organization.mcp_enabled  # Add this field
    }
    
    result = await db.organizations.insert_one(org_doc)
    return Organization(**{
        **org_doc,
        "id": str(result.inserted_id)
    })
    

@app.put("/v0/account/organizations/{organization_id}", response_model=Organization, tags=["account/organizations"])
async def update_organization(
    organization_id: str,
    organization_update: OrganizationUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update an organization (account admin or organization admin)"""
    ad.log.info(f"Updating organization {organization_id} with {organization_update}")
    db = ad.common.get_async_db()

    organization = await db.organizations.find_one({"_id": ObjectId(organization_id)})
    if not organization:
        ad.log.error(f"Organization not found: {organization_id}")
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if user has permission (account admin or organization admin)
    db_user = await db.users.find_one({"_id": ObjectId(current_user.user_id)})
    is_account_admin = db_user and db_user.get("role") == "admin"
    is_organization_admin = any(member["role"] == "admin" and member["user_id"] == current_user.user_id for member in organization["members"])
    
    if not (is_account_admin or is_organization_admin):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update this organization"
        )

    # Is the type changing?
    if organization_update.type is not None and organization_update.type != organization["type"]:
        ad.log.info(f"Updating organization type from {organization['type']} to {organization_update.type}")
        await organizations.update_organization_type(
            db=db,
            organization_id=organization_id,
            update=organization_update
        )

    # Build update document
    update_doc = {"updated_at": datetime.utcnow()}
    if organization_update.name is not None:
        update_doc["name"] = organization_update.name
    if organization_update.type is not None:
        update_doc["type"] = organization_update.type
    if organization_update.members is not None:
        # Ensure at least one admin remains
        if not any(m.role == "admin" for m in organization_update.members):
            ad.log.error(f"Organization must have at least one admin: {organization_update.members}")
            raise HTTPException(
                status_code=400,
                detail="Organization must have at least one admin"
            )
        update_doc["members"] = [m.dict() for m in organization_update.members]

    if organization_update.mcp_enabled is not None:
        update_doc["mcp_enabled"] = organization_update.mcp_enabled
    
    # Use find_one_and_update instead of update_one to get the updated document atomically
    updated_organization = await db.organizations.find_one_and_update(
        {"_id": ObjectId(organization_id)},
        {"$set": update_doc},
        return_document=True  # Return the updated document
    )
    
    if not updated_organization:
        ad.log.error(f"Organization not found after update: {organization_id}")
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return Organization(**{
        "id": str(updated_organization["_id"]),
        "name": updated_organization["name"],
        "members": updated_organization["members"],
        "type": updated_organization["type"],
        "created_at": updated_organization["created_at"],
        "updated_at": updated_organization["updated_at"]
    })
    

@app.delete("/v0/account/organizations/{organization_id}", tags=["account/organizations"])
async def delete_organization(
    organization_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete an organization (account admin or organization admin)"""
    # Get organization and verify it exists
    db = ad.common.get_async_db()
    organization = await db.organizations.find_one({"_id": ObjectId(organization_id)})
    if not organization:
        raise HTTPException(404, "Organization not found")
    
    # Check if user has permission (account admin or organization admin)
    db_user = await db.users.find_one({"_id": ObjectId(current_user.user_id)})
    is_account_admin = db_user and db_user.get("role") == "admin"
    is_organization_admin = any(member["role"] == "admin" and member["user_id"] == current_user.user_id for member in organization["members"])
    
    if not (is_account_admin or is_organization_admin):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this organization"
        )
        
    await db.organizations.delete_one({"_id": ObjectId(organization_id)})
    return {"status": "success"}

    return {"message": "Organization deleted"}

# Add these new endpoints after the existing ones
@app.get("/v0/account/users", response_model=ListUsersResponse, tags=["account/users"])
async def list_users(
    organization_id: str | None = Query(None, description="Filter users by organization ID"),
    user_id: str | None = Query(None, description="Get a specific user by ID"),
    skip: int = Query(0, description="Number of users to skip"),
    limit: int = Query(10, description="Number of users to return"),
    current_user: User = Depends(get_current_user)
):
    """
    List users or get a specific user.
    - If user_id is provided, returns just that user (requires proper permissions)
    - If organization_id is provided, returns users from that organization
    - Otherwise returns all users (admin only)
    - user_id and organization_id are mutually exclusive
    """
    db = ad.common.get_async_db()
    db_user = await db.users.find_one({"_id": ObjectId(current_user.user_id)})
    is_system_admin = db_user and db_user.get("role") == "admin"

    # user_id and organization_id are mutually exclusive
    if user_id and organization_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both user_id and organization_id"
        )

    # Base query
    query = {}
    
    # Handle single user request
    if user_id:
        try:
            user = await db.users.find_one({"_id": ObjectId(user_id)})
        except:
            raise HTTPException(status_code=404, detail="User not found")
            
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check permissions
        is_self = current_user.user_id == user_id
        
        if not (is_system_admin or is_self):
            # Check if user is an org admin for any org the target user is in
            user_orgs = await db.organizations.find({
                "members.user_id": user_id
            }).to_list(None)
            
            is_org_admin = any(
                any(m["user_id"] == current_user.user_id and m["role"] == "admin" 
                    for m in org["members"])
                for org in user_orgs
            )
            
            if not is_org_admin:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to view this user"
                )
                
        return ListUsersResponse(
            users=[UserResponse(
                id=str(user["_id"]),
                email=user["email"],
                name=user.get("name"),
                role=user.get("role", "user"),
                emailVerified=user.get("emailVerified"),
                createdAt=user.get("createdAt", datetime.now(UTC)),
                hasPassword=bool(user.get("password"))
            )],
            total_count=1,
            skip=0
        )

    # Handle organization filter
    if organization_id:
        org = await db.organizations.find_one({"_id": ObjectId(organization_id)})
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
            
        is_org_admin = any(
            m["user_id"] == current_user.user_id and m["role"] == "admin" 
            for m in org["members"]
        )
        
        if not (is_system_admin or is_org_admin):
            raise HTTPException(
                status_code=403, 
                detail="Not authorized to view organization users"
            )
            
        member_ids = [m["user_id"] for m in org["members"]]
        query["_id"] = {"$in": [ObjectId(uid) for uid in member_ids]}
    elif not is_system_admin:
        # List all users in organizations the current user is an admin of
        orgs = await db.organizations.find({
            "members.user_id": current_user.user_id,
            "members.role": "admin"
        }).to_list(None)
        member_ids = [m["user_id"] for org in orgs for m in org["members"]]
        
        # Add the current user to the list of users, if they are not already in the list
        if current_user.user_id not in member_ids:
            member_ids.append(current_user.user_id)
        
        query["_id"] = {"$in": [ObjectId(uid) for uid in member_ids]}
    else:
        # A system admin can list all users. No need to filter by organization.
        pass

    total_count = await db.users.count_documents(query)
    users = await db.users.find(query).skip(skip).limit(limit).to_list(None)

    return ListUsersResponse(
        users=[
            UserResponse(
                id=str(user["_id"]),
                email=user["email"],
                name=user.get("name"),
                role=user.get("role", "user"),
                emailVerified=user.get("emailVerified"),
                createdAt=user.get("createdAt", datetime.now(UTC)),
                hasPassword=bool(user.get("password"))
            )
            for user in users
        ],
        total_count=total_count,
        skip=skip
    )

@app.post("/v0/account/users", response_model=UserResponse, tags=["account/users"])
async def create_user(
    user: UserCreate,
    current_user: User = Depends(get_admin_user)
):
    """Create a new user (admin only)"""
    db = ad.common.get_async_db()
    # Check total users limit
    total_users = await db.users.count_documents({})
    if total_users >= limits.MAX_TOTAL_USERS:
        raise HTTPException(
            status_code=403,
            detail="System limit reached: Maximum number of users exceeded"
        )

    # Check if email already exists
    if await db.users.find_one({"email": user.email}):
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    # Check if an organization exists with same name as the user email
    existing_org = await db.organizations.find_one({"name": user.email})
    if existing_org:
        raise HTTPException(
            status_code=400,
            detail=f"An organization with the same name as the user email ({user.email}) already exists"
        )
    
    # Hash password
    hashed_password = hashpw(user.password.encode(), gensalt(12))
    
    # Create user document with default role
    user_doc = {
        "email": user.email,
        "name": user.name,
        "password": hashed_password.decode(),
        "role": "user",  # Always set default role as user
        "emailVerified": True,
        "createdAt": datetime.now(UTC),
        "hasSeenTour": False
    }
    
    result = await db.users.insert_one(user_doc)
    user_doc["id"] = str(result.inserted_id)
    user_doc["hasPassword"] = True
    
    # Create default individual organization for new user
    await db.organizations.insert_one({
        "_id": result.inserted_id,
        "name": user.email,
        "members": [{
            "user_id": str(result.inserted_id),
            "role": "admin"
        }],
        "type": "individual",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    })
    
    # Create corresponding payments customer
    await get_or_create_payments_customer(
        user_id=str(user_doc["_id"]),
        email=user.email,
        name=user.name
    )
    
    return UserResponse(**user_doc)

@app.put("/v0/account/users/{user_id}", response_model=UserResponse, tags=["account/users"])
async def update_user(
    user_id: str,
    user: UserUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update a user's details (admin or self)"""
    db = ad.common.get_async_db()
    # Check if user has permission (admin or self)
    db_current_user = await db.users.find_one({"_id": ObjectId(current_user.user_id)})
    is_admin = db_current_user.get("role") == "admin"
    is_self = current_user.user_id == user_id
    
    if not (is_admin or is_self):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update this user"
        )
    
    # For self-updates, only allow name changes
    update_data = {}
    if is_self and not is_admin:
        if user.name is not None:
            update_data["name"] = user.name
        if user.password is not None:
            update_data["password"] = hashpw(user.password.encode(), gensalt(12)).decode()
        if user.hasSeenTour is not None:
            update_data["hasSeenTour"] = user.hasSeenTour
    else:
        # Admin can update all fields
        update_data = {
            k: v for k, v in user.model_dump().items() 
            if v is not None
        }
        
        # If password is included, hash it
        if "password" in update_data:
            update_data["password"] = hashpw(update_data["password"].encode(), gensalt(12)).decode()
        
        # Don't allow updating the last admin user to non-admin
        if user.role == "user":
            admin_count = await db.users.count_documents({"role": "admin"})
            target_user = await db.users.find_one({"_id": ObjectId(user_id)})
            if admin_count == 1 and target_user and target_user.get("role") == "admin":
                raise HTTPException(
                    status_code=400,
                    detail="Cannot remove admin role from the last admin user"
                )
    
    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No valid update data provided"
        )
    
    result = await db.users.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": update_data},
        return_document=True
    )
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    # Update payments customer if email or name changed
    if (user.name):
        await update_payments_customer(
            user_id=user_id,
            name=user.name,
        )
    
    return UserResponse(
        id=str(result["_id"]),
        email=result["email"],
        name=result.get("name"),
        role=result.get("role", "user"),
        emailVerified=result.get("emailVerified"),
        createdAt=result.get("createdAt", datetime.now(UTC)),
        hasPassword=bool(result.get("password"))
    )


@app.delete("/v0/account/users/{user_id}", tags=["account/users"])
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a user (admin or self)"""
    db = ad.common.get_async_db()

    # Check if user has permission (admin or self)
    db_current_user = await db.users.find_one({"_id": ObjectId(current_user.user_id)})
    is_admin = db_current_user.get("role") == "admin"
    is_self = current_user.user_id == user_id
    
    if not (is_admin or is_self):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this user"
        )
    
    # Don't allow deleting the last admin user
    target_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target_user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    if target_user.get("role") == "admin":
        admin_count = await db.users.count_documents({"role": "admin"})
        if admin_count == 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last admin user"
            )
    
    # Handle payments customer before deleting user
    await delete_payments_customer(user_id)
    
    try:
        await users.delete_user(db, user_id)
        return {"message": "User and related data deleted successfully"}
    except Exception as e:
        ad.log.error(f"Error deleting user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete user and related data"
        )

@app.post("/v0/account/email/verification/register/{user_id}", tags=["account/email"])
async def send_registration_verification_email(user_id: str):
    """Send verification email for newly registered users (no auth required)"""
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.get("emailVerified"):
        raise HTTPException(status_code=400, detail="Email already verified")

    # Generate verification token
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(UTC) + timedelta(hours=24)).replace(tzinfo=UTC)
    
    # Store verification token
    await db.email_verifications.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "token": token,
                "expires": expires,
                "email": user["email"]
            }
        },
        upsert=True
    )
        
    verification_url = f"{NEXTAUTH_URL}/auth/verify-email?token={token}"
    
    html_content = email_utils.get_verification_email_content(
        verification_url=verification_url,
        site_url=NEXTAUTH_URL,
        user_name=user.get("name")
    )
        
    # Use the send_email utility function instead of direct SES client call
    await email_utils.send_email(
        analytiq_client,
        to_email=user["email"],
        from_email=SES_FROM_EMAIL,
        subject=email_utils.get_email_subject("verification"),
        content=html_content,
    )
    
    return {"message": "Registration email sent"}


@app.post("/v0/account/email/verification/send/{user_id}", tags=["account/email"])
async def send_verification_email(
    user_id: str,
    current_user: User = Depends(get_admin_user)
):
    """Send verification email (admin only)"""
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.get("emailVerified"):
        raise HTTPException(status_code=400, detail="Email already verified")

    # Generate verification token
    token = secrets.token_urlsafe(32)
    # Ensure expiration time is stored with UTC timezone
    expires = (datetime.now(UTC) + timedelta(hours=24)).replace(tzinfo=UTC)
    
    # Store verification token
    await db.email_verifications.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "token": token,
                "expires": expires,
                "email": user["email"]
            }
        },
        upsert=True
    )
        
    verification_url = f"{NEXTAUTH_URL}/auth/verify-email?token={token}"
    
    # Get email content from template
    html_content = email_utils.get_verification_email_content(
        verification_url=verification_url,
        site_url=NEXTAUTH_URL,
        user_name=user.get("name")
    )
        
    # Use the send_email utility function instead of direct SES client call
    await email_utils.send_email(
        analytiq_client,
        to_email=user["email"],
        from_email=SES_FROM_EMAIL,
        subject=email_utils.get_email_subject("verification"),
        content=html_content,
    )

    return {"message": "Verification email sent"}

@app.post("/v0/account/email/verification/{token}", tags=["account/email"])
async def verify_email(token: str, background_tasks: BackgroundTasks):
    """Verify email address using token"""
    ad.log.info(f"Verifying email with token: {token}")
    db = ad.common.get_async_db()

    # Find verification record
    verification = await db.email_verifications.find_one({"token": token})
    if not verification:
        ad.log.info(f"No verification record found for token: {token}")
        raise HTTPException(status_code=400, detail="Invalid verification token")
        
    # Check if token expired
    # Convert stored expiration to UTC for comparison
    stored_expiry = verification["expires"].replace(tzinfo=UTC)
    if stored_expiry < datetime.now(UTC):
        ad.log.info(f"Verification token expired: {stored_expiry} < {datetime.now(UTC)}")
        raise HTTPException(status_code=400, detail="Verification token expired")
    
    # Update user's email verification status
    updated_user = await db.users.find_one_and_update(
        {"_id": ObjectId(verification["user_id"])},
        {"$set": {"emailVerified": True}},
        return_document=True
    )

    if not updated_user:
        ad.log.info(f"Failed to verify email for user {verification['user_id']}")
        raise HTTPException(status_code=404, detail="User not found")
    
    if updated_user.get("emailVerified"):
        return {"message": "Email already verified"}

    # Allow the user to re-verify their email for 1 minute
    ad.log.info(f"Scheduling deletion of verification record for token: {token}")
    async def delete_verification_later():
        await asyncio.sleep(60)  # Wait 60 seconds
        await db.email_verifications.delete_one({"token": token})
        ad.log.info(f"Deleted verification record for token: {token}")

    background_tasks.add_task(delete_verification_later)
    
    return {"message": "Email verified successfully"}

@app.post("/v0/account/email/invitations", response_model=InvitationResponse, tags=["account/email"])
async def create_invitation(
    invitation: CreateInvitationRequest,
    current_user: User = Depends(get_admin_user)
):
    """Create a new invitation (admin only)"""
    ad.log.info(f"Got invitation request: {invitation}")
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)

    # Check if email already registered, if so, set user_exists to True
    existing_user = await db.users.find_one({"email": invitation.email})
    if existing_user:
        user_exists = True
    else:
        user_exists = False
    
    if user_exists:
        if invitation.organization_id:
            # Check if user is already in the organization
            org = await db.organizations.find_one({
                "_id": ObjectId(invitation.organization_id),
                "members.user_id": existing_user["_id"]
            })
            if org:
                raise HTTPException(status_code=400, detail="User is already a member of this organization")
        else:
            # User already exists, and this is not an org invitation
            raise HTTPException(status_code=400, detail="User already exists")

    if await db.users.find_one({"email": invitation.email}):
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
        
    # If there's an existing pending invitation for the same organization, invalidate it
    query = {
        "email": invitation.email,
        "status": "pending",
        "expires": {"$gt": datetime.now(UTC)}
    }
    
    # Only add organization_id to query if it exists
    if invitation.organization_id:
        query["organization_id"] = invitation.organization_id
    else:
        # If this is not an org invitation, only invalidate other non-org invitations
        query["organization_id"] = {"$exists": False}

    await db.invitations.update_many(
        query,
        {"$set": {"status": "invalidated"}}
    )

    # Generate invitation token
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(hours=24)
    
    # Create invitation document
    invitation_doc = {
        "email": invitation.email,
        "token": token,
        "status": "pending",
        "expires": expires,
        "created_by": current_user.user_id,
        "created_at": datetime.now(UTC),
        "user_exists": user_exists
    }
    
    # Get organization name if this is an org invitation
    organization_name = None
    if invitation.organization_id:
        invitation_doc["organization_id"] = invitation.organization_id
        
        org = await db.organizations.find_one({"_id": ObjectId(invitation.organization_id)})
        if org:
            organization_name = org["name"]
    
    result = await db.invitations.insert_one(invitation_doc)
    invitation_doc["id"] = str(result.inserted_id)
    
    # Send invitation email
    invitation_url = f"{NEXTAUTH_URL}/auth/accept-invitation?token={token}"
    html_content = email_utils.get_invitation_email_content(
        invitation_url=invitation_url,
        site_url=NEXTAUTH_URL,
        expires=expires,
        organization_name=organization_name
    )
    
    try:
        # Send invitation email using the email_utils.send_email() utility function
        await email_utils.send_email(
            analytiq_client,
            to_email=invitation.email,
            from_email=SES_FROM_EMAIL,
            subject=email_utils.get_email_subject("invitation"),
            content=html_content,
        )
        return InvitationResponse(**invitation_doc)
    except Exception as e:
        ad.log.error(f"Failed to send invitation email: {str(e)}")
        # Delete invitation if email fails
        await db.invitations.delete_one({"_id": result.inserted_id})
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send invitation email: {str(e)}"
        )

@app.get("/v0/account/email/invitations", response_model=ListInvitationsResponse, tags=["account/email"])
async def list_invitations(
    skip: int = Query(0),
    limit: int = Query(10),
    current_user: User = Depends(get_admin_user)
):
    """List all invitations (admin only)"""
    db = ad.common.get_async_db()
    query = {}
    total_count = await db.invitations.count_documents(query)
    cursor = db.invitations.find(query).skip(skip).limit(limit)
    invitations = await cursor.to_list(None)
    
    return ListInvitationsResponse(
        invitations=[
            InvitationResponse(
                id=str(inv["_id"]),
                email=inv["email"],
                status=inv["status"],
                expires=inv["expires"],
                created_by=inv["created_by"],
                created_at=inv["created_at"],
                organization_id=inv.get("organization_id"),
                organization_role=inv.get("organization_role")
            )
            for inv in invitations
        ],
        total_count=total_count,
        skip=skip
    )

@app.get("/v0/account/email/invitations/{token}", response_model=InvitationResponse, tags=["account/email"])
async def get_invitation(token: str):
    """Get invitation details by token"""
    db = ad.common.get_async_db()
    invitation = await db.invitations.find_one({
        "token": token,
        "status": "pending"
    })
    
    if not invitation:
        raise HTTPException(
            status_code=404,
            detail="Invalid or expired invitation"
        )
        
    # Ensure both datetimes are timezone-aware for comparison
    invitation_expires = invitation["expires"].replace(tzinfo=UTC)
    if invitation_expires < datetime.now(UTC):
        await db.invitations.update_one(
            {"_id": invitation["_id"]},
            {"$set": {"status": "expired"}}
        )
        raise HTTPException(
            status_code=400,
            detail="Invitation has expired"
        )

    # Check if user already exists
    user_exists = await db.users.find_one({"email": invitation["email"]}) is not None

    # Get organization name if this is an org invitation
    organization_name = None
    if invitation.get("organization_id"):
        org = await db.organizations.find_one({"_id": ObjectId(invitation["organization_id"])})
        if org:
            organization_name = org["name"]
    
    return InvitationResponse(
        id=str(invitation["_id"]),
        email=invitation["email"],
        status=invitation["status"],
        expires=invitation["expires"],
        created_by=invitation["created_by"],
        created_at=invitation["created_at"],
        organization_id=invitation.get("organization_id"),
        organization_name=organization_name,  # Add organization name
        user_exists=user_exists  # Add user existence status
    )

@app.post("/v0/account/email/invitations/{token}/accept", tags=["account/email"])
async def accept_invitation(
    token: str,
    data: AcceptInvitationRequest = Body(...)  # Change to use AcceptInvitationRequest
):
    """Accept an invitation and create user account if needed"""
    ad.log.info(f"Accepting invitation with token: {token}")
    db = ad.common.get_async_db()
    # Find and validate invitation
    invitation = await db.invitations.find_one({
        "token": token,
        "status": "pending"
    })
    
    if not invitation:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired invitation"
        )
        
    # Ensure both datetimes are timezone-aware for comparison
    invitation_expires = invitation["expires"].replace(tzinfo=UTC)
    if invitation_expires < datetime.now(UTC):
        await db.invitations.update_one(
            {"_id": invitation["_id"]},
            {"$set": {"status": "expired"}}
        )
        raise HTTPException(
            status_code=400,
            detail="Invitation has expired"
        )
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": invitation["email"]})
    
    if existing_user:
        user_id = str(existing_user["_id"])
        
        # If this is an organization invitation, add user to the organization
        if invitation.get("organization_id"):
            # Check if user is already in the organization
            org = await db.organizations.find_one({
                "_id": ObjectId(invitation["organization_id"]),
                "members.user_id": user_id
            })
            
            if org:
                raise HTTPException(
                    status_code=400,
                    detail="User is already a member of this organization"
                )
            
            # Add user to organization
            await db.organizations.update_one(
                {"_id": ObjectId(invitation["organization_id"])},
                {
                    "$push": {
                        "members": {
                            "user_id": user_id,
                            "role": "user"  # Default all invited users to regular member role
                        }
                    }
                }
            )
        
        # Mark invitation as accepted
        await db.invitations.update_one(
            {"_id": invitation["_id"]},
            {"$set": {"status": "accepted"}}
        )
        
        return {"message": "User added to organization successfully"}
    
    # Create new user account if they don't exist
    if not data.name or not data.password:
        raise HTTPException(
            status_code=400,
            detail="Name and password are required for new accounts"
        )

    hashed_password = hashpw(data.password.encode(), gensalt(12))
    user_doc = {
        "email": invitation["email"],
        "name": data.name,
        "password": hashed_password.decode(),
        "role": "user",  # Default all invited users to regular user role
        "emailVerified": True,  # Auto-verify since it's from invitation
        "createdAt": datetime.now(UTC)
    }
    
    try:
        result = await db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        
        # If organization invitation, add to organization
        if invitation.get("organization_id"):
            await db.organizations.update_one(
                {"_id": ObjectId(invitation["organization_id"])},
                {
                    "$push": {
                        "members": {
                            "user_id": user_id,
                            "role": "user"  # Default all invited users to regular member role
                        }
                    }
                }
            )
        else:
            # Create default individual organization
            await db.organizations.insert_one({
                "_id": result.inserted_id,
                "name": invitation["email"],
                "members": [{
                    "user_id": user_id,
                    "role": "admin"  # User is admin of their individual org
                }],
                "type": "individual",
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC)
            })
        
        # Mark invitation as accepted
        await db.invitations.update_one(
            {"_id": invitation["_id"]},
            {"$set": {"status": "accepted"}}
        )
        
        # Create corresponding payments customer
        await get_or_create_payments_customer(
            user_id=user_id,
            email=invitation["email"],
            name=data.name
        )  
        
        return {"message": "Account created successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create account: {str(e)}"
        )

# Account-level access tokens
@app.post("/v0/account/access_tokens", response_model=AccessToken, tags=["account/access_tokens"])
async def create_account_token(
    request: CreateAccessTokenRequest,
    current_user: User = Depends(get_current_user)
):
    """Create an account-level API token"""
    ad.log.debug(f"Creating account token for user: {current_user} request: {request}")
    db = ad.common.get_async_db()

    token = secrets.token_urlsafe(32)
    new_token = {
        "user_id": current_user.user_id,
        "organization_id": None,  # Explicitly set to None for account-level tokens
        "name": request.name,
        "token": ad.crypto.encrypt_token(token),
        "created_at": datetime.now(UTC),
        "lifetime": request.lifetime
    }
    result = await db.access_tokens.insert_one(new_token)

    new_token["token"] = token  # Return plaintext token to user
    new_token["id"] = str(result.inserted_id)
    return new_token

@app.get("/v0/account/access_tokens", response_model=ListAccessTokensResponse, tags=["account/access_tokens"])
async def list_account_tokens(
    current_user: User = Depends(get_current_user)
):
    """List account-level API tokens"""
    db = ad.common.get_async_db()
    
    cursor = db.access_tokens.find({
        "user_id": current_user.user_id,
        "organization_id": None  # Only get account-level tokens
    })
    tokens = await cursor.to_list(length=None)
    ret = [
        {
            "id": str(token["_id"]),
            "user_id": token["user_id"],
            "organization_id": None,
            "name": token["name"],
            "token": token["token"],
            "created_at": token["created_at"],
            "lifetime": token["lifetime"]
        }
        for token in tokens
    ]
    return ListAccessTokensResponse(access_tokens=ret)

@app.delete("/v0/account/access_tokens/{token_id}", tags=["account/access_tokens"])
async def delete_account_token(
    token_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete an account-level API token"""
    db = ad.common.get_async_db()
    
    result = await db.access_tokens.delete_one({
        "_id": ObjectId(token_id),
        "user_id": current_user.user_id,
        "organization_id": None  # Only delete account-level tokens
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token deleted successfully"}

# Include payments router only if STRIPE_SECRET_KEY is set
if os.getenv("STRIPE_SECRET_KEY"):
    app.include_router(payments_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="::", port=8000)
