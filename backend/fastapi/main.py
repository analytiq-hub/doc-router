# main.py

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Depends, status, Body, Security, Response
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

import api
import models
from schemas import (
    User,
    AccessToken, ListAccessTokensResponse, CreateAccessTokenRequest,
    ListDocumentsResponse,
    DocumentMetadata,
    DocumentUpload, DocumentsUpload,
    LLMToken, CreateLLMTokenRequest, ListLLMTokensResponse,
    AWSCredentials,
    OCRMetadataResponse,
    LLMRunResponse, LLMResult,
    Schema, SchemaCreate, ListSchemasResponse,
    Prompt, PromptCreate, ListPromptsResponse,
)

# Add the parent directory to the sys path
sys.path.append("..")
import analytiq_data as ad

# Set up the environment variables. This reads the .env file.
ad.common.setup()

# Initialize the logger
ad.init_logger("fastapi")

# Environment variables
ENV = os.getenv("ENV", "dev")
NEXTAUTH_URL = os.getenv("NEXTAUTH_URL")
FASTAPI_ROOT_PATH = os.getenv("FASTAPI_ROOT_PATH", "/")

ad.log.info(f"ENV: {ENV}")
ad.log.info(f"NEXTAUTH_URL: {NEXTAUTH_URL}")
ad.log.info(f"FASTAPI_ROOT_PATH: {FASTAPI_ROOT_PATH}")

# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
UPLOAD_DIR = "data"

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

# MongoDB connection
analytiq_client = ad.common.get_analytiq_client(env=ENV)
db_name = ENV
db = analytiq_client.mongodb_async[db_name]
job_queue_collection = db.job_queue
access_token_collection = db.access_tokens
llm_token_collection = db.llm_tokens
aws_credentials_collection = db.aws_credentials
schemas_collection = db.schemas
schema_versions_collection = db.schema_versions
prompts_collection = db.prompts
prompt_versions_collection = db.prompt_versions

from pydantic import BaseModel

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        # First, try to validate as JWT
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        userId: str = payload.get("userId")
        userName: str = payload.get("userName")
        email: str = payload.get("email")
        ad.log.info(f"get_current_user(): userId: {userId}, userName: {userName}, email: {email}")
        if userName is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return User(user_id=userId,
                    user_name=userName,
                    token_type="jwt")
    except JWTError:
        # If JWT validation fails, check if it's an API token
        access_token = await access_token_collection.find_one({"token": token})
        ad.log.info(f"get_current_user(): access_token: {access_token}")
        if access_token:
            return User(user_id=access_token["user_id"],
                        user_name=access_token["name"],
                        token_type="api")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

# PDF management endpoints
@app.post("/documents")
async def upload_document(
    documents_upload: DocumentsUpload = Body(...),
    current_user: User = Depends(get_current_user)
):
    ad.log.info(f"upload_document(): documents: {[doc.name for doc in documents_upload.files]}")
    uploaded_documents = []
    for document in documents_upload.files:
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
        ad.common.save_file(analytiq_client,
                            file_name=mongo_file_name,
                            blob=content,
                            metadata=metadata)

        document_metadata = {
            "_id": ObjectId(document_id),
            "user_file_name": document.name,
            "mongo_file_name": mongo_file_name,
            "document_id": document_id,
            "upload_date": datetime.utcnow(),
            "uploaded_by": current_user.user_name,
            "state": "Uploaded"
        }
        
        await ad.common.save_doc(analytiq_client, document_metadata)
        uploaded_documents.append({"document_name": document.name, "document_id": document_id})

        # Post a message to the ocr job queue
        msg = {"document_id": document_id}
        await ad.queue.send_msg(analytiq_client, "ocr", msg=msg)
    
    return {"uploaded_documents": uploaded_documents}

@app.get("/documents/list", response_model=ListDocumentsResponse)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user: User = Depends(get_current_user)
):
    documents, total_count = await ad.common.list_docs(analytiq_client, skip=skip, limit=limit)
    
    return ListDocumentsResponse(
        documents=[
            {
                "id": str(doc["_id"]),
                "document_name": doc["user_file_name"],
                "upload_date": doc["upload_date"].isoformat(),
                "uploaded_by": doc["uploaded_by"],
                "state": doc.get("state", "")
            }
            for doc in documents
        ],
        total_count=total_count,
        skip=skip
    )

@app.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    ad.log.info(f"get_document() start: document_id: {document_id}")
    document = await ad.common.get_doc(analytiq_client, document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    ad.log.info(f"get_document() found document: {document}")

    # Get the file from mongodb
    file = ad.common.get_file(analytiq_client, document["mongo_file_name"])
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")

    ad.log.info(f"get_document() got file: {document}")

    # Make sure we're sending the correct content type for PDFs
    return Response(
        content=file["blob"],
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={document['user_file_name']}",
            "Content-Length": str(file["metadata"]["size"]),
            "Cache-Control": "no-cache"
        }
    )

@app.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    document = await ad.common.get_doc(analytiq_client, document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if "mongo_file_name" not in document:
        raise HTTPException(
            status_code=500, 
            detail="Document metadata is corrupted: missing mongo_file_name"
        )

    ad.common.delete_file(analytiq_client, file_name=document["mongo_file_name"])
    await ad.common.delete_doc(analytiq_client, document_id)

    return {"message": "Document deleted successfully"}

@app.post("/access_tokens", response_model=AccessToken)
async def access_token_create(
    request: CreateAccessTokenRequest,
    current_user: User = Depends(get_current_user)
):
    ad.log.info(f"Creating API token for user: {current_user} request: {request}")
    token = secrets.token_urlsafe(32)
    new_token = {
        "user_id": current_user.user_id,
        "name": request.name,
        "token": token,
        "created_at": datetime.now(UTC),
        "lifetime": request.lifetime
    }
    result = await access_token_collection.insert_one(new_token)
    new_token["id"] = str(result.inserted_id)
    return new_token

@app.get("/access_tokens", response_model=ListAccessTokensResponse)
async def access_token_list(current_user: User = Depends(get_current_user)):
    cursor = access_token_collection.find({"user_id": current_user.user_id})
    tokens = await cursor.to_list(length=None)
    ret = [
        {
            "id": str(token["_id"]),
            "user_id": token["user_id"],
            "name": token["name"],
            "token": token["token"],
            "created_at": token["created_at"],
            "lifetime": token["lifetime"]
        }
        for token in tokens
    ]
    ad.log.info(f"list_access_tokens(): {ret}")
    return ListAccessTokensResponse(access_tokens=ret)

@app.delete("/access_tokens/{token_id}")
async def access_token_delete(
    token_id: str,
    current_user: User = Depends(get_current_user)
):
    result = await access_token_collection.delete_one({
        "_id": ObjectId(token_id),
        "user_id": current_user.user_id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token deleted successfully"}

@app.post("/llm_tokens", response_model=LLMToken)
async def llm_token_create(
    request: CreateLLMTokenRequest,
    current_user: User = Depends(get_current_user)
):
    ad.log.info(f"Creating/Updating LLM token for user: {current_user} request: {request}")
    
    # Check if a token for this vendor already exists
    existing_token = await llm_token_collection.find_one({
        "user_id": current_user.user_id,
        "llm_vendor": request.llm_vendor
    })

    new_token = {
        "user_id": current_user.user_id,
        "llm_vendor": request.llm_vendor,
        "token": request.token,
        "created_at": datetime.now(UTC),
    }

    if existing_token:
        # Update the existing token
        result = await llm_token_collection.replace_one(
            {"_id": existing_token["_id"]},
            new_token
        )
        new_token["id"] = str(existing_token["_id"])
        ad.log.info(f"Updated existing LLM token for {request.llm_vendor}")
    else:
        # Insert a new token
        result = await llm_token_collection.insert_one(new_token)
        new_token["id"] = str(result.inserted_id)
        ad.log.info(f"Created new LLM token for {request.llm_vendor}")

    return new_token

@app.get("/llm_tokens", response_model=ListLLMTokensResponse)
async def llm_token_list(current_user: User = Depends(get_current_user)):
    cursor = llm_token_collection.find({"user_id": current_user.user_id})
    tokens = await cursor.to_list(length=None)
    llm_tokens = [
        {
            "id": str(token["_id"]),
            "user_id": token["user_id"],
            "llm_vendor": token["llm_vendor"],
            "token": token["token"],
            "created_at": token["created_at"],
        }
        for token in tokens
    ]
    ad.log.info(f"list_llm_tokens(): {llm_tokens}")
    return ListLLMTokensResponse(llm_tokens=llm_tokens)

@app.delete("/llm_tokens/{token_id}")
async def llm_token_delete(
    token_id: str,
    current_user: User = Depends(get_current_user)
):
    result = await llm_token_collection.delete_one({
        "_id": ObjectId(token_id),
        "user_id": current_user.user_id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="LLM Token not found")
    return {"message": "LLM Token deleted successfully"}

@app.post("/aws_credentials")
async def aws_credentials_create(
    request: AWSCredentials,
    current_user: User = Depends(get_current_user)
):
    ad.log.info(f"Creating/Updating AWS credentials for user: {current_user}")

    # Validate AWS Access Key ID format
    if not re.match(r'^[A-Z0-9]{20}$', request.access_key_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid AWS Access Key ID format. Must be 20 characters long and contain only uppercase letters and numbers."
        )

    # Validate AWS Secret Access Key format
    if not re.match(r'^[A-Za-z0-9+/]{40}$', request.secret_access_key):
        raise HTTPException(
            status_code=400,
            detail="Invalid AWS Secret Access Key format. Must be 40 characters long and contain only letters, numbers, and +/."
        )

    aws_credentials = {
        "access_key_id": request.access_key_id,
        "secret_access_key": request.secret_access_key,
        "user_id": current_user.user_id,
        "created_at": datetime.now(UTC),
    }
    # Replace the existing credentials if they already exist
    existing_credentials = await aws_credentials_collection.find_one({
        "user_id": current_user.user_id
    })
    if existing_credentials:
        result = await aws_credentials_collection.replace_one(
            {"_id": existing_credentials["_id"]},
            aws_credentials
        )
    else:
        result = await aws_credentials_collection.insert_one(aws_credentials)
    return {"message": "AWS credentials created successfully"}


@app.get("/aws_credentials", response_model=AWSCredentials)
async def aws_credentials_get(current_user: User = Depends(get_current_user)):
    ad.log.info(f"Getting AWS credentials for user: {current_user}")
    aws_credentials = await aws_credentials_collection.find_one({
        "user_id": current_user.user_id
    })
    
    if not aws_credentials:
        raise HTTPException(status_code=404, detail="AWS credentials not found")
    
    # Block the secret access key
    aws_credentials["secret_access_key"] = "********"

    return aws_credentials

@app.delete("/aws_credentials")
async def aws_credentials_delete(current_user: User = Depends(get_current_user)):
    ad.log.info(f"Deleting AWS credentials for user: {current_user}")
    result = await aws_credentials_collection.delete_one({
        "user_id": current_user.user_id
    })
    return {"message": "AWS credentials deleted successfully"}

@app.post("/auth/token")
async def create_auth_token(user_data: dict = Body(...)):
    ad.log.info(f"create_auth_token(): user_data: {user_data}")
    token = jwt.encode(
        {
            "userId": user_data["sub"],
            "userName": user_data["name"],
            "email": user_data["email"]
        },
        JWT_SECRET,
        algorithm=ALGORITHM
    )
    return {"token": token}

@app.get("/ocr/download/blocks/{document_id}")
async def download_ocr_blocks(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    ad.log.info(f"download_ocr_blocks() start: document_id: {document_id}")

    document = await ad.common.get_doc(analytiq_client, document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get the OCR JSON data from mongodb
    ocr_list = ad.common.get_ocr_list(analytiq_client, document_id)
    if ocr_list is None:
        raise HTTPException(status_code=404, detail="OCR data not found")
    
    return JSONResponse(content=ocr_list)

@app.get("/ocr/download/text/{document_id}", response_model=str)
async def download_ocr_text(
    document_id: str,
    page_num: Optional[int] = Query(None, description="Specific page number to retrieve"),
    current_user: User = Depends(get_current_user)
):
    ad.log.info(f"download_ocr_text() start: document_id: {document_id}, page_num: {page_num}")
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

@app.get("/ocr/download/metadata/{document_id}", response_model=OCRMetadataResponse)
async def get_ocr_metadata(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    ad.log.info(f"get_ocr_metadata() start: document_id: {document_id}")
    
    document = await ad.common.get_doc(analytiq_client, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get the OCR metadata from mongodb
    metadata = ad.common.get_ocr_metadata(analytiq_client, document_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="OCR metadata not found")
    
    return OCRMetadataResponse(
        n_pages=metadata["n_pages"],
        ocr_date=metadata["ocr_date"].isoformat()
    )

# LLM Run Endpoints
@app.post("/llm/run/{document_id}", response_model=LLMRunResponse)
async def run_llm_analysis(
    document_id: str,
    prompt_id: str = Query(default="document_info", description="The prompt ID to use"),
    force: bool = Query(default=False, description="Force new run even if result exists"),
    current_user: User = Depends(get_current_user)
):
    """
    Run LLM on a document, with optional force refresh.
    
    Args:
        document_id: The document ID to process
        prompt_id: The prompt ID to use (defaults to "document_info")
        force: If True, forces a new run even if cached result exists
    """
    ad.log.info(f"run_llm_analysis() start: document_id: {document_id}, prompt_id: {prompt_id}, force: {force}")
    
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

@app.get("/llm/result/{document_id}", response_model=LLMResult)
async def get_llm_result(
    document_id: str,
    prompt_id: str = Query(default="document_info", description="The prompt ID to retrieve"),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve existing LLM results for a document.
    """
    ad.log.info(f"get_llm_result() start: document_id: {document_id}, prompt_id: {prompt_id}")
    
    # Verify document exists and user has access
    document = await ad.common.get_doc(analytiq_client, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    result = await ad.llm.get_llm_result(analytiq_client, document_id, prompt_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"LLM result not found for document_id: {document_id} and prompt_id: {prompt_id}"
        )
    
    return result

@app.delete("/llm/result/{document_id}")
async def delete_llm_result(
    document_id: str,
    prompt_id: str = Query(..., description="The prompt ID to delete"),
    current_user: User = Depends(get_current_user)
):
    """
    Delete LLM results for a specific document and prompt.
    """
    ad.log.info(f"delete_llm_result() start: document_id: {document_id}, prompt_id: {prompt_id}")
    
    # Verify document exists and user has access
    document = await ad.common.get_doc(analytiq_client, document_id)
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
async def get_next_schema_version(schema_name: str) -> int:
    """Atomically get the next version number for a schema"""
    result = await schema_versions_collection.find_one_and_update(
        {"_id": schema_name},
        {"$inc": {"version": 1}},
        upsert=True,
        return_document=True
    )
    return result["version"]

# Schema management endpoints
@app.post("/api/schemas", response_model=Schema)
async def create_schema(
    schema: SchemaCreate,
    current_user: User = Depends(get_current_user)
):
    # Check if schema with this name already exists (case-insensitive)
    existing_schema = await schemas_collection.find_one({
        "name": {"$regex": f"^{schema.name}$", "$options": "i"}
    })
    
    # If schema exists, treat this as an update operation
    if existing_schema:
        # Get the next version
        new_version = await get_next_schema_version(schema.name)
        
        # Create new version of the schema
        schema_dict = {
            "name": existing_schema["name"],  # Use existing name to preserve case
            "fields": [field.model_dump() for field in schema.fields],
            "version": new_version,
            "created_at": datetime.utcnow(),
            "created_by": current_user.user_id
        }
    else:
        # This is a new schema
        new_version = await get_next_schema_version(schema.name)
        schema_dict = {
            "name": schema.name,
            "fields": [field.model_dump() for field in schema.fields],
            "version": new_version,
            "created_at": datetime.utcnow(),
            "created_by": current_user.user_id
        }
    
    # Insert into MongoDB
    result = await schemas_collection.insert_one(schema_dict)
    
    # Return complete schema
    schema_dict["id"] = str(result.inserted_id)
    return Schema(**schema_dict)

@app.get("/api/schemas", response_model=ListSchemasResponse)
async def list_schemas(current_user: User = Depends(get_current_user)):
    # Pipeline to get only the latest version of each schema
    pipeline = [
        {
            "$sort": {"name": 1, "version": -1}
        },
        {
            "$group": {
                "_id": "$name",
                "doc": {"$first": "$$ROOT"}
            }
        },
        {
            "$replaceRoot": {"newRoot": "$doc"}
        }
    ]
    
    cursor = schemas_collection.aggregate(pipeline)
    schemas = await cursor.to_list(length=None)
    
    # Convert _id to id in each schema and ensure version is included
    for schema in schemas:
        schema['id'] = str(schema.pop('_id'))
        # version is already included from MongoDB doc, no need to add it
    
    return ListSchemasResponse(schemas=schemas)

@app.get("/api/schemas/{schema_id}", response_model=Schema)
async def get_schema(
    schema_id: str,
    current_user: User = Depends(get_current_user)
):
    schema = await schemas_collection.find_one({"_id": ObjectId(schema_id)})
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    schema['id'] = str(schema.pop('_id'))
    # version is already included from MongoDB doc, no need to add it
    return Schema(**schema)

@app.put("/api/schemas/{schema_id}", response_model=Schema)
async def update_schema(
    schema_id: str,
    schema: SchemaCreate,
    current_user: User = Depends(get_current_user)
):
    # Get the existing schema
    existing_schema = await schemas_collection.find_one({"_id": ObjectId(schema_id)})
    if not existing_schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    # Check if user has permission to update
    if existing_schema["created_by"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this schema")
    
    # Validate field names
    is_valid, error_msg = validate_schema_fields(schema.fields)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=error_msg
        )
    
    # Atomically get the next version number
    new_version = await get_next_schema_version(existing_schema["name"])
    
    # Create new version of the schema
    new_schema = {
        "name": schema.name,
        "fields": [field.model_dump() for field in schema.fields],
        "version": new_version,
        "created_at": datetime.utcnow(),
        "created_by": current_user.user_id
    }
    
    # Insert new version
    result = await schemas_collection.insert_one(new_schema)
    
    # Return updated schema
    new_schema["id"] = str(result.inserted_id)
    return Schema(**new_schema)

@app.delete("/api/schemas/{schema_id}")
async def delete_schema(
    schema_id: str,
    current_user: User = Depends(get_current_user)
):
    # Get the schema to find its name
    schema = await schemas_collection.find_one({"_id": ObjectId(schema_id)})
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    if schema["created_by"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this schema")
    
    # Check for dependent prompts
    dependent_prompts = await prompts_collection.find({
        "schema_name": schema["name"]
    }).to_list(length=None)
    
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
    result = await schemas_collection.delete_many({"name": schema["name"]})
    
    # Also delete the version counter
    await schema_versions_collection.delete_one({"_id": schema["name"]})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {"message": "Schema deleted successfully"}

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
async def get_next_prompt_version(prompt_name: str) -> int:
    """Atomically get the next version number for a prompt"""
    result = await prompt_versions_collection.find_one_and_update(
        {"_id": prompt_name},
        {"$inc": {"version": 1}},
        upsert=True,
        return_document=True
    )
    return result["version"]

# Prompt management endpoints
@app.post("/api/prompts", response_model=Prompt)
async def create_prompt(
    prompt: PromptCreate,
    current_user: User = Depends(get_current_user)
):
    # Only verify schema if one is specified
    if prompt.schema_name and prompt.schema_version:
        schema = await schemas_collection.find_one({
            "name": prompt.schema_name,
            "version": prompt.schema_version
        })
        if not schema:
            raise HTTPException(
                status_code=404,
                detail=f"Schema {prompt.schema_name} version {prompt.schema_version} not found"
            )

    # Check if prompt with this name already exists (case-insensitive)
    existing_prompt = await prompts_collection.find_one({
        "name": {"$regex": f"^{prompt.name}$", "$options": "i"}
    })
    
    # Get the next version
    new_version = await get_next_prompt_version(prompt.name)
    
    # Create prompt document
    prompt_dict = {
        "name": existing_prompt["name"] if existing_prompt else prompt.name,
        "content": prompt.content,
        "schema_name": prompt.schema_name or "",  # Use empty string if None
        "schema_version": prompt.schema_version or 0,  # Use 0 if None
        "version": new_version,
        "created_at": datetime.utcnow(),
        "created_by": current_user.user_id
    }
    
    # Insert into MongoDB
    result = await prompts_collection.insert_one(prompt_dict)
    
    # Return complete prompt
    prompt_dict["id"] = str(result.inserted_id)
    return Prompt(**prompt_dict)

@app.get("/api/prompts", response_model=ListPromptsResponse)
async def list_prompts(current_user: User = Depends(get_current_user)):
    # Pipeline to get only the latest version of each prompt
    pipeline = [
        {
            "$sort": {"name": 1, "version": -1}
        },
        {
            "$group": {
                "_id": "$name",
                "doc": {"$first": "$$ROOT"}
            }
        },
        {
            "$replaceRoot": {"newRoot": "$doc"}
        }
    ]
    
    cursor = prompts_collection.aggregate(pipeline)
    prompts = await cursor.to_list(length=None)
    
    # Convert _id to id in each prompt
    for prompt in prompts:
        prompt['id'] = str(prompt.pop('_id'))
    
    return ListPromptsResponse(prompts=prompts)

@app.get("/api/prompts/{prompt_id}", response_model=Prompt)
async def get_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_user)
):
    prompt = await prompts_collection.find_one({"_id": ObjectId(prompt_id)})
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    prompt['id'] = str(prompt.pop('_id'))
    return Prompt(**prompt)

@app.put("/api/prompts/{prompt_id}", response_model=Prompt)
async def update_prompt(
    prompt_id: str,
    prompt: PromptCreate,
    current_user: User = Depends(get_current_user)
):
    # Get the existing prompt
    existing_prompt = await prompts_collection.find_one({"_id": ObjectId(prompt_id)})
    if not existing_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # Check if user has permission to update
    if existing_prompt["created_by"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this prompt")
    
    # Verify schema exists
    schema = await schemas_collection.find_one({
        "name": prompt.schema_name,
        "version": prompt.schema_version
    })
    if not schema:
        raise HTTPException(
            status_code=404,
            detail=f"Schema {prompt.schema_name} version {prompt.schema_version} not found"
        )
    
    # Get the next version number
    new_version = await get_next_prompt_version(existing_prompt["name"])
    
    # Create new version of the prompt
    new_prompt = {
        "name": prompt.name,
        "content": prompt.content,
        "schema_name": prompt.schema_name,
        "schema_version": prompt.schema_version,
        "version": new_version,
        "created_at": datetime.utcnow(),
        "created_by": current_user.user_id
    }
    
    # Insert new version
    result = await prompts_collection.insert_one(new_prompt)
    
    # Return updated prompt
    new_prompt["id"] = str(result.inserted_id)
    return Prompt(**new_prompt)

@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_user)
):
    # Get the prompt to find its name
    prompt = await prompts_collection.find_one({"_id": ObjectId(prompt_id)})
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    if prompt["created_by"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this prompt")
    
    # Delete all versions of this prompt
    result = await prompts_collection.delete_many({"name": prompt["name"]})
    
    # Also delete the version counter
    await prompt_versions_collection.delete_one({"_id": prompt["name"]})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"message": "Prompt deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="::", port=8000)
