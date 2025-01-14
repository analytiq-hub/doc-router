from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse, Response
from datetime import datetime
from bson import ObjectId
import base64

import analytiq_data as ad
from setup import get_async_db, get_analytiq_client
from auth import get_current_user
from schemas import (
    DocumentsUpload,
    DocumentUpdate,
    ListDocumentsResponse,
    DocumentResponse,
    DocumentMetadata,
    User
)

documents_router = APIRouter(
    prefix="/documents",
    tags=["documents"]
)

@documents_router.post("")
async def upload_document(
    documents_upload: DocumentsUpload = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Upload one or more documents"""
    ad.log.debug(f"upload_document(): documents: {[doc.name for doc in documents_upload.files]}")
    uploaded_documents = []
    
    db = get_async_db()
    analytiq_client = get_analytiq_client()

    # Validate all tag IDs first
    all_tag_ids = set()
    for document in documents_upload.files:
        all_tag_ids.update(document.tag_ids)
    
    if all_tag_ids:
        # Check if all tags exist and belong to the user
        tags_cursor = db.tags.find({
            "_id": {"$in": [ObjectId(tag_id) for tag_id in all_tag_ids]},
            "created_by": current_user.user_id
        })
        existing_tags = await tags_cursor.to_list(None)
        existing_tag_ids = {str(tag["_id"]) for tag in existing_tags}
        
        invalid_tags = all_tag_ids - existing_tag_ids
        if invalid_tags:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tag IDs: {list(invalid_tags)}"
            )

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
            "state": ad.common.doc.DOCUMENT_STATE_UPLOADED,
            "tag_ids": document.tag_ids
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

@documents_router.put("/{document_id}")
async def update_document(
    document_id: str,
    update: DocumentUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update a document"""
    ad.log.debug(f"Updating document {document_id} with data: {update}")
    
    analytiq_client = get_analytiq_client()
    db = get_async_db()

    # Validate the document exists and user has access
    document = await ad.common.get_doc(analytiq_client, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document["uploaded_by"] != current_user.user_name:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to modify this document"
        )

    # Validate all tag IDs
    if update.tag_ids:
        tags_cursor = db.tags.find({
            "_id": {"$in": [ObjectId(tag_id) for tag_id in update.tag_ids]},
            "created_by": current_user.user_id
        })
        existing_tags = await tags_cursor.to_list(None)
        existing_tag_ids = {str(tag["_id"]) for tag in existing_tags}
        
        invalid_tags = set(update.tag_ids) - existing_tag_ids
        if invalid_tags:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tag IDs: {list(invalid_tags)}"
            )

    # Update the document
    updated_doc = await db.docs.find_one_and_update(
        {"_id": ObjectId(document_id)},
        {"$set": {"tag_ids": update.tag_ids}},
        return_document=True
    )

    if not updated_doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    return {"message": "Document tags updated successfully"}

@documents_router.get("", response_model=ListDocumentsResponse)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    tag_ids: str = Query(None, description="Comma-separated list of tag IDs"),
    user: User = Depends(get_current_user)
):
    """List documents"""
    db = get_async_db()
    
    # Build the query filter
    query_filter = {}
    
    # Add tag filtering if tag_ids are provided
    if tag_ids:
        tag_id_list = [tid.strip() for tid in tag_ids.split(",")]
        query_filter["tag_ids"] = {"$all": tag_id_list}
    
    # Get total count with filters
    total_count = await db.docs.count_documents(query_filter)
    
    # Get paginated documents with sorting and filters
    cursor = db.docs.find(query_filter).sort("_id", -1).skip(skip).limit(limit)
    documents = await cursor.to_list(length=None)
    
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

@documents_router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a document"""
    analytiq_client = get_analytiq_client()
    
    ad.log.debug(f"get_document() start: document_id: {document_id}")
    document = await ad.common.get_doc(analytiq_client, document_id)
    
    if not document:
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

@documents_router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a document"""
    analytiq_client = get_analytiq_client()
    
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