# documents.py

# Standard library imports
from datetime import datetime, UTC
import os
import base64
import logging
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from bson import ObjectId

# Local imports
import analytiq_data as ad
from analytiq_data.common.doc import get_mime_type
from app.auth import get_org_user
from app.models import User

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
documents_router = APIRouter(tags=["documents"])

# Document models
class DocumentUpload(BaseModel):
    name: str
    content: str
    tag_ids: List[str] = []  # Optional list of tag IDs
    metadata: Optional[Dict[str, str]] = {}  # Optional key-value metadata pairs

class DocumentsUpload(BaseModel):
    documents: List[DocumentUpload]

class DocumentMetadata(BaseModel):
    id: str
    pdf_id: str
    document_name: str
    upload_date: datetime
    uploaded_by: str
    state: str
    tag_ids: List[str] = []  # List of tag IDs
    type: str | None = None   # MIME type of the returned file (original/pdf)
    metadata: Optional[Dict[str, str]] = {}  # Optional key-value metadata pairs

class DocumentResponse(BaseModel):
    id: str
    pdf_id: str
    document_name: str
    upload_date: datetime
    uploaded_by: str
    state: str
    tag_ids: List[str] = []  # List of tag IDs
    type: str | None = None   # MIME type of the returned file (original/pdf)
    metadata: Optional[Dict[str, str]] = {}  # Optional key-value metadata pairs
    content: str  # Base64 encoded content

    model_config = ConfigDict(arbitrary_types_allowed=True)

class ListDocumentsResponse(BaseModel):
    documents: List[DocumentMetadata]
    total_count: int
    skip: int

class DocumentUpdate(BaseModel):
    """Schema for updating document metadata"""
    document_name: Optional[str] = Field(
        default=None,
        description="New name for the document"
    )
    tag_ids: Optional[List[str]] = Field(
        default=None,
        description="List of tag IDs associated with the document"
    )
    metadata: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional key-value metadata pairs"
    )

def decode_base64_content(content: str) -> bytes:
    """
    Decode base64 content that may be either:
    1. A data URL: 'data:application/pdf;base64,JVBERi0xLjQK...'
    2. Plain base64: 'JVBERi0xLjQK...'
    """
    try:
        # Check if it's a data URL
        if content.startswith('data:'):
            # Extract the base64 part after the comma
            base64_part = content.split(',', 1)[1]
            return base64.b64decode(base64_part)
        else:
            # Assume it's plain base64
            return base64.b64decode(content)
    except (IndexError, ValueError) as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid base64 content: {str(e)}"
        )

@documents_router.post("/v0/orgs/{organization_id}/documents")
async def upload_document(
    organization_id: str,
    documents_upload: DocumentsUpload = Body(...),
    current_user: User = Depends(get_org_user)
):
    """Upload one or more documents"""
    logger.debug(f"upload_document(): documents: {[doc.name for doc in documents_upload.documents]}")
    documents = []

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
        try:
            mime_type = get_mime_type(document.name)
            ext = os.path.splitext(document.name)[1].lower()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        content = decode_base64_content(document.content)
        document_id = ad.common.create_id()
        mongo_file_name = f"{document_id}{ext}"

        metadata = {
            "document_id": document_id,
            "type": mime_type,
            "size": len(content),
            "user_file_name": document.name
        }

        # Save the document to mongodb
        await ad.common.save_file_async(analytiq_client,
                                        file_name=mongo_file_name,
                                        blob=content,
                                        metadata=metadata)

        if mime_type == "application/pdf":
            pdf_id = document_id
            pdf_file_name = mongo_file_name
        else:
            # Convert to PDF and save
            pdf_blob = ad.common.file.convert_to_pdf(content, ext)  # You will implement this function
            pdf_id = ad.common.create_id()
            pdf_file_name = f"{pdf_id}.pdf"
            await ad.common.save_file_async(analytiq_client, pdf_file_name, pdf_blob, metadata)

        document_metadata = {
            "_id": ObjectId(document_id),
            "user_file_name": document.name,
            "mongo_file_name": mongo_file_name,
            "document_id": document_id,
            "pdf_id": pdf_id,
            "pdf_file_name": pdf_file_name,
            "upload_date": datetime.now(UTC),
            "uploaded_by": current_user.user_name,
            "state": ad.common.doc.DOCUMENT_STATE_UPLOADED,
            "tag_ids": document.tag_ids,
            "metadata": document.metadata,
            "organization_id": organization_id
        }
        
        await ad.common.save_doc(analytiq_client, document_metadata)
        documents.append({
            "document_name": document.name,
            "document_id": document_id,
            "tag_ids": document.tag_ids,
            "metadata": document.metadata
        })

        # Post a message to the ocr job queue
        msg = {"document_id": document_id}
        await ad.queue.send_msg(analytiq_client, "ocr", msg=msg)
    
    return {"documents": documents}

@documents_router.put("/v0/orgs/{organization_id}/documents/{document_id}")
async def update_document(
    organization_id: str,
    document_id: str,
    update: DocumentUpdate,
    current_user: User = Depends(get_org_user)
):
    """Update a document"""
    logger.info(f"Updating document {document_id} with data: {update}")
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
    if update.tag_ids is not None:
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
    if update.tag_ids is not None:
        update_dict["tag_ids"] = update.tag_ids
    
    # Add document_name to update if provided
    if update.document_name is not None:
        update_dict["user_file_name"] = update.document_name
    
    # Add metadata to update if provided
    if update.metadata is not None:
        update_dict["metadata"] = update.metadata
    
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

@documents_router.get("/v0/orgs/{organization_id}/documents", response_model=ListDocumentsResponse)
async def list_documents(
    organization_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    tag_ids: str = Query(None, description="Comma-separated list of tag IDs"),
    name_search: str = Query(None, description="Search term for document names"),
    metadata_search: str = Query(None, description="Metadata search as key=value pairs, comma-separated (e.g., 'author=John,type=invoice'). Special characters in keys/values are URL-encoded automatically."),
    current_user: User = Depends(get_org_user)
):
    """List documents within an organization"""
    # Get analytiq client
    analytiq_client = ad.common.get_analytiq_client()
    
    tag_id_list = [tid.strip() for tid in tag_ids.split(",")] if tag_ids else None
    
    # Parse metadata search parameters
    metadata_search_dict = None
    if metadata_search:
        from urllib.parse import unquote
        metadata_search_dict = {}
        for pair in metadata_search.split(","):
            # Only strip leading whitespace to handle spacing around commas
            # Don't strip trailing whitespace as it might be part of the search value
            pair = pair.lstrip()
            # URL decode the pair first to handle encoded = signs
            decoded_pair = unquote(pair)
            if "=" in decoded_pair:
                key, value = decoded_pair.split("=", 1)
                # Strip whitespace from key but preserve value as-is
                metadata_search_dict[key.strip()] = value
    
    docs, total_count = await ad.common.list_docs(
        analytiq_client,
        organization_id=organization_id,
        skip=skip,
        limit=limit,
        tag_ids=tag_id_list,
        name_search=name_search,
        metadata_search=metadata_search_dict
    )
    
    return ListDocumentsResponse(
        documents=[
            DocumentMetadata(
                id=str(doc["_id"]),
                pdf_id=doc.get("pdf_id", doc.get("document_id", str(doc["_id"]))),  # fallback for old docs
                document_name=doc.get("user_file_name", doc.get("document_name", "")),
                upload_date=doc["upload_date"].replace(tzinfo=UTC).isoformat() if isinstance(doc["upload_date"], datetime) else doc["upload_date"],
                uploaded_by=doc.get("uploaded_by", ""),
                state=doc.get("state", ""),
                tag_ids=doc.get("tag_ids", []),
                metadata=doc.get("metadata", {}),
                # Optionally add pdf_file_name if you want to expose it
            )
            for doc in docs
        ],
        total_count=total_count,
        skip=skip
    )

@documents_router.get("/v0/orgs/{organization_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    organization_id: str,
    document_id: str,
    file_type: str = Query(default="original", 
                           enum=["original", "pdf"], 
                           description="Which file to retrieve: 'original' or 'pdf'"),
    current_user: User = Depends(get_org_user)
):
    """Get a document (original or associated PDF)"""
    logger.debug(f"get_document() start: document_id: {document_id}, file_type: {file_type}")
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)

    # Get document with organization scope
    document = await db.docs.find_one({
        "_id": ObjectId(document_id),
        "organization_id": organization_id
    })
    
    if not document:
        logger.debug(f"get_document() document not found: {document}")
        raise HTTPException(status_code=404, detail="Document not found")
        
    logger.debug(f"get_document() found document: {document}")

    # Decide which file to return
    if file_type == "pdf":
        file_name = document.get("pdf_file_name", document.get("mongo_file_name"))
    else:
        file_name = document.get("mongo_file_name")

    # Get the file from mongodb
    file = await ad.common.get_file_async(analytiq_client, file_name)
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")

    logger.debug(f"get_document() got file: {file_name}")

    # Determine MIME type for the file being returned
    # Prefer stored metadata.type; fall back to inferring from original name
    try:
        returned_mime = file["metadata"].get("type")
    except Exception:
        returned_mime = None
    if not returned_mime:
        try:
            returned_mime = get_mime_type(document["user_file_name"])
        except Exception:
            returned_mime = None

    # Return flattened response
    return DocumentResponse(
        id=str(document["_id"]),
        pdf_id=document.get("pdf_id", document["document_id"]),
        document_name=document["user_file_name"],
        upload_date=document["upload_date"].replace(tzinfo=UTC),
        uploaded_by=document["uploaded_by"],
        state=document.get("state", ""),
        tag_ids=document.get("tag_ids", []),
        type=returned_mime,
        metadata=document.get("metadata", {}),
        content=base64.b64encode(file["blob"]).decode('utf-8')
    )

@documents_router.delete("/v0/orgs/{organization_id}/documents/{document_id}")
async def delete_document(
    organization_id: str,
    document_id: str,
    current_user: User = Depends(get_org_user)
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

    # Delete the original file
    await ad.common.delete_file_async(analytiq_client, file_name=document["mongo_file_name"])

    # Delete the associated PDF if it's different
    pdf_file_name = document.get("pdf_file_name")
    if pdf_file_name and pdf_file_name != document["mongo_file_name"]:
        await ad.common.delete_file_async(analytiq_client, file_name=pdf_file_name)

    await ad.common.delete_doc(analytiq_client, document_id, organization_id)
    
    return {"message": "Document deleted successfully"}
