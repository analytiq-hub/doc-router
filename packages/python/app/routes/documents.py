# documents.py
from __future__ import annotations

# Standard library imports
from datetime import datetime, UTC
import os
import json
import base64
import logging
from typing import Optional, List, Dict, Annotated, Any

from pydantic import BaseModel, Field, ConfigDict

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, Body, File, Form, UploadFile
from fastapi.responses import Response
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
    content: Optional[str] = None  # Base64 encoded content; omitted when include_content=false (backward compatible: default request returns content)

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


async def _validate_tag_ids_for_org(
    organization_id: str,
    all_tag_ids: set[str],
    db,
) -> None:
    if not all_tag_ids:
        return
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


async def _save_single_uploaded_document(
    analytiq_client,
    organization_id: str,
    current_user: User,
    name: str,
    content: bytes,
    tag_ids: List[str],
    metadata: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    """Persist one decoded file (same storage path as JSON upload)."""
    if metadata is None:
        metadata = {}
    try:
        mime_type = get_mime_type(name)
        ext = os.path.splitext(name)[1].lower()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    document_id = ad.common.create_id()
    mongo_file_name = f"{document_id}{ext}"

    file_metadata = {
        "document_id": document_id,
        "type": mime_type,
        "size": len(content),
        "user_file_name": name
    }

    await ad.common.save_file_async(
        analytiq_client,
        file_name=mongo_file_name,
        blob=content,
        metadata=file_metadata,
    )

    if mime_type == "application/pdf":
        pdf_id = document_id
        pdf_file_name = mongo_file_name
    else:
        pdf_blob = ad.common.file.convert_to_pdf(content, ext)
        pdf_id = ad.common.create_id()
        pdf_file_name = f"{pdf_id}.pdf"
        await ad.common.save_file_async(analytiq_client, pdf_file_name, pdf_blob, file_metadata)

    document_metadata = {
        "_id": ObjectId(document_id),
        "user_file_name": name,
        "mongo_file_name": mongo_file_name,
        "document_id": document_id,
        "pdf_id": pdf_id,
        "pdf_file_name": pdf_file_name,
        "upload_date": datetime.now(UTC),
        "uploaded_by": current_user.user_name,
        "state": ad.common.doc.DOCUMENT_STATE_UPLOADED,
        "tag_ids": tag_ids,
        "metadata": metadata,
        "organization_id": organization_id
    }

    await ad.common.save_doc(analytiq_client, document_metadata)

    logger.info(f"upload_document(): saved {organization_id}/{document_id} name {name}")

    try:
        await ad.webhooks.enqueue_event(
            analytiq_client,
            organization_id=organization_id,
            event_type="document.uploaded",
            document_id=document_id,
        )
    except Exception as e:
        logger.warning(f"Webhook enqueue failed for uploaded doc {document_id}: {e}")

    await ad.queue.send_msg(analytiq_client, "ocr", msg={"document_id": document_id})

    return {
        "document_name": name,
        "document_id": document_id,
        "tag_ids": tag_ids,
        "metadata": metadata,
    }


@documents_router.post("/v0/orgs/{organization_id}/documents")
async def upload_document(
    organization_id: str,
    documents_upload: DocumentsUpload = Body(...),
    current_user: User = Depends(get_org_user)
):
    """Upload one or more documents"""
    logger.info(f"upload_document(): {organization_id}: uploading documents: {[doc.name for doc in documents_upload.documents]}")
    documents = []

    all_tag_ids = set()
    for document in documents_upload.documents:
        all_tag_ids.update(document.tag_ids)

    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    await _validate_tag_ids_for_org(organization_id, all_tag_ids, db)

    for document in documents_upload.documents:
        content = decode_base64_content(document.content)
        documents.append(
            await _save_single_uploaded_document(
                analytiq_client,
                organization_id,
                current_user,
                document.name,
                content,
                document.tag_ids,
                document.metadata,
            )
        )

    return {"documents": documents}


@documents_router.post("/v0/orgs/{organization_id}/documents/multipart")
async def upload_document_multipart(
    organization_id: str,
    files: Annotated[
        list[UploadFile],
        File(description="Binary bodies; repeat form field name 'files' for multiple uploads."),
    ],
    manifest: Annotated[
        Optional[str],
        Form(
            description=(
                "Optional JSON array, one object per file in the same order as parts. "
                "Each object may include: name (str), tag_ids (list[str]), metadata (object). "
                "Omitted keys fall back to the part's filename and empty tag_ids/metadata."
            )
        ),
    ] = None,
    current_user: User = Depends(get_org_user),
):
    """
    Upload one or more documents as raw multipart file parts (no base64, no giant JSON).

    More efficient than POST /documents for large PDFs: avoids ~33% base64 expansion and
    large JSON parse on the server.
    """
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    if manifest is not None and manifest.strip():
        try:
            parsed = json.loads(manifest)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid manifest JSON: {e}")
        if not isinstance(parsed, list):
            raise HTTPException(status_code=400, detail="manifest must be a JSON array")
        if len(parsed) != len(files):
            raise HTTPException(
                status_code=400,
                detail=f"manifest length {len(parsed)} must match number of file parts {len(files)}",
            )
        entries: List[Any] = parsed
    else:
        entries = [{} for _ in files]

    all_tag_ids: set[str] = set()
    resolved: list[tuple[str, List[str], Dict[str, str]]] = []
    for i, file in enumerate(files):
        spec = entries[i]
        if not isinstance(spec, dict):
            raise HTTPException(
                status_code=400,
                detail=f"manifest[{i}] must be a JSON object if manifest is provided",
            )
        name = spec.get("name") or file.filename
        if not name:
            raise HTTPException(
                status_code=400,
                detail=f"File part {i} needs a filename or manifest[{i}].name",
            )
        raw_tags = spec.get("tag_ids", [])
        if raw_tags is None:
            raw_tags = []
        if not isinstance(raw_tags, list) or not all(isinstance(t, str) for t in raw_tags):
            raise HTTPException(status_code=400, detail=f"manifest[{i}].tag_ids must be a list of strings")
        raw_meta = spec.get("metadata", {})
        if raw_meta is None:
            raw_meta = {}
        if not isinstance(raw_meta, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in raw_meta.items()
        ):
            raise HTTPException(
                status_code=400,
                detail=f"manifest[{i}].metadata must be a string-to-string map",
            )
        all_tag_ids.update(raw_tags)
        resolved.append((name, raw_tags, raw_meta))

    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    await _validate_tag_ids_for_org(organization_id, all_tag_ids, db)

    logger.info(
        "upload_document_multipart(): %s: %s file(s): %s",
        organization_id,
        len(files),
        [r[0] for r in resolved],
    )

    documents: List[Dict[str, Any]] = []
    for file, (name, tag_ids, meta) in zip(files, resolved):
        content = await file.read()
        documents.append(
            await _save_single_uploaded_document(
                analytiq_client,
                organization_id,
                current_user,
                name,
                content,
                tag_ids,
                meta,
            )
        )

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

    # Get old tag IDs before update (for KB membership check)
    old_tag_ids = document.get("tag_ids", [])
    
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
    
    # If tags changed, trigger KB membership re-evaluation
    if update.tag_ids is not None:
        new_tag_ids = set(update.tag_ids)
        old_tag_ids_set = set(old_tag_ids)
        
        if new_tag_ids != old_tag_ids_set:
            # Tags changed - queue KB indexing job to re-evaluate membership
            # The worker will handle both adding to new KBs and removing from old KBs
            kb_msg = {"document_id": document_id}
            await ad.queue.send_msg(analytiq_client, "kb_index", msg=kb_msg)
            logger.info(f"Queued KB indexing for document {document_id} due to tag changes")
            
            # If tags were removed, reconcile only this document across KBs
            removed_tag_ids = old_tag_ids_set - new_tag_ids
            
            if removed_tag_ids:
                # Reconcile only this document (not full KB reconciliation)
                # This will check if the document needs to be removed from any KBs
                try:
                    await ad.kb.reconciliation.reconcile_knowledge_base(
                        analytiq_client=analytiq_client,
                        organization_id=organization_id,
                        doc_id=document_id,
                        dry_run=False
                    )
                    logger.info(f"Auto-reconciled document {document_id} after tag removal")
                except Exception as e:
                    # Log error but don't fail the document update
                    logger.error(f"Error auto-reconciling document {document_id} after tag removal: {e}")

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
    include_content: bool = Query(
        True,
        description="If false, return only metadata without file content (e.g. for polling). Default true for backward compatibility.",
    ),
    current_user: User = Depends(get_org_user)
):
    """Get a document (original or associated PDF). Use include_content=false for metadata-only (no file download)."""
    logger.debug(f"get_document() start: document_id: {document_id}, file_type: {file_type}, include_content: {include_content}")
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

    # Metadata-only path: no file fetch (backward compatible: default include_content=True still returns content)
    if not include_content:
        try:
            returned_mime = get_mime_type(document["user_file_name"])
        except Exception:
            returned_mime = None
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
            content=None,
        )

    # Full response: resolve file and return content
    if file_type == "pdf":
        file_name = document.get("pdf_file_name", document.get("mongo_file_name"))
    else:
        file_name = document.get("mongo_file_name")

    file = await ad.common.get_file_async(analytiq_client, file_name)
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")

    logger.debug(f"get_document() got file: {file_name}")

    try:
        returned_mime = file["metadata"].get("type")
    except Exception:
        returned_mime = None
    if not returned_mime:
        try:
            returned_mime = get_mime_type(document["user_file_name"])
        except Exception:
            returned_mime = None

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
        content=base64.b64encode(file["blob"]).decode("utf-8"),
    )

@documents_router.get("/v0/orgs/{organization_id}/documents/{document_id}/file")
async def get_document_file(
    organization_id: str,
    document_id: str,
    file_type: str = Query(default="pdf", enum=["original", "pdf"]),
    current_user: User = Depends(get_org_user)
):
    """Return the raw binary of the document file (no base64). Use file_type=pdf for the PDF version."""
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)

    document = await db.docs.find_one({
        "_id": ObjectId(document_id),
        "organization_id": organization_id
    })
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if file_type == "pdf":
        file_name = document.get("pdf_file_name", document.get("mongo_file_name"))
    else:
        file_name = document.get("mongo_file_name")

    file = await ad.common.get_file_async(analytiq_client, file_name)
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        media_type = file["metadata"].get("type") or "application/octet-stream"
    except Exception:
        media_type = "application/octet-stream"

    user_file_name = document.get("user_file_name", file_name)
    headers = {"Content-Disposition": f'attachment; filename="{user_file_name}"'}
    return Response(content=file["blob"], media_type=media_type, headers=headers)


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
