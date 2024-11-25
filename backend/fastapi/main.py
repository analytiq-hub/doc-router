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

import api
import models
from schemas import (
    User,
    AccessToken, ListAccessTokensResponse, CreateAccessTokenRequest,
    ListPDFsResponse,
    PDFMetadata,
    FileUpload, FilesUpload,
    LLMToken, CreateLLMTokenRequest, ListLLMTokensResponse,
    AWSCredentials,
    OCRMetadataResponse,
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
db_name = "prod" if ENV == "prod" else "dev"
db = analytiq_client.mongodb_async[db_name]
job_queue_collection = db.job_queue
access_token_collection = db.access_tokens
llm_token_collection = db.llm_tokens
aws_credentials_collection = db.aws_credentials

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
@app.post("/files/upload")
async def upload_file(
    files_upload: FilesUpload = Body(...),
    current_user: User = Depends(get_current_user)
):
    ad.log.info(f"upload_pdf(): files: {[file.name for file in files_upload.files]}")
    uploaded_files = []
    for file in files_upload.files:
        if not file.name.endswith('.pdf'):
            raise HTTPException(status_code=400, detail=f"File {file.name} is not a PDF")
        
        # Decode and save the file
        content = base64.b64decode(file.content.split(',')[1])

        # Create a unique id for the document
        document_id = ad.common.create_id()
        mongo_file_name = f"{document_id}.pdf"

        metadata = {
            "document_id": document_id,
            "type": "application/pdf",
            "size": len(content),
            "user_file_name": file.name
        }

        # Save the file to mongodb
        ad.common.save_file(analytiq_client,
                            file_name=mongo_file_name,
                            blob=content,
                            metadata=metadata)

        document = {
            "_id": ObjectId(document_id),
            "user_file_name": file.name,
            "mongo_file_name": mongo_file_name,
            "document_id": document_id,
            "upload_date": datetime.utcnow(),
            "uploaded_by": current_user.user_name,
            "state": "Uploaded"
        }
        
        await ad.common.save_doc(analytiq_client, document)
        uploaded_files.append({"file_name": file.name, "document_id": document_id})

        # Post a message to the ocr job queue
        msg = {"document_id": document_id}
        await ad.queue.send_msg(analytiq_client, "ocr", msg=msg)
    
    return {"uploaded_files": uploaded_files}

@app.get("/files/download/{document_id}")
async def download_file(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    ad.log.info(f"download_file() start: document_id: {document_id}")
    document = await ad.common.get_doc(analytiq_client, document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    ad.log.info(f"download_file() found document: {document}")

    # Get the file from mongodb
    file = ad.common.get_file(analytiq_client, document["mongo_file_name"])
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")

    ad.log.info(f"download_file() got file: {document}")

    ret = Response(
        content=file["blob"],
        media_type=file["metadata"]["type"],
        headers={
            "Content-Disposition": f"attachment; filename={document['user_file_name']}",
            "Content-Length": str(file["metadata"]["size"])
        }
    )
    
    ad.log.info(f"download_file() end: {ret}")
    return ret

@app.get("/files/list", response_model=ListPDFsResponse)
async def list_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user: User = Depends(get_current_user)
):
    documents, total_count = await ad.common.list_docs(analytiq_client, skip=skip, limit=limit)
    
    return ListPDFsResponse(
        pdfs=[
            {
                "id": str(doc["_id"]),
                "file_name": doc["user_file_name"],
                "upload_date": doc["upload_date"].isoformat(),
                "uploaded_by": doc["uploaded_by"],
                "state": doc.get("state", "")
            }
            for doc in documents
        ],
        total_count=total_count,
        skip=skip
    )

@app.delete("/files/delete/{file_id}", response_model=None)
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user)
):
    document = await ad.common.get_doc(analytiq_client, file_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    ad.common.delete_file(analytiq_client, file_name=document["mongo_file_name"])
    await ad.common.delete_doc(analytiq_client, file_id)

    return

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

@app.get("/ocr/download/metadata/{document_id}", response_model=OCRMetadata)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="::", port=8000)
