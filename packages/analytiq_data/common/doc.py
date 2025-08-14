from datetime import datetime, UTC
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging

import analytiq_data as ad

logger = logging.getLogger(__name__)

DOCUMENT_STATE_UPLOADED = "uploaded"
DOCUMENT_STATE_OCR_PROCESSING = "ocr_processing" 
DOCUMENT_STATE_OCR_COMPLETED = "ocr_completed"
DOCUMENT_STATE_OCR_FAILED = "ocr_failed"
DOCUMENT_STATE_LLM_PROCESSING = "llm_processing"
DOCUMENT_STATE_LLM_COMPLETED = "llm_completed"
DOCUMENT_STATE_LLM_FAILED = "llm_failed"

EXTENSION_TO_MIME = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc":  "application/msword",
    ".csv":  "text/csv",
    ".xls":  "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt":  "text/plain",
    ".md":   "text/markdown",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".gif":  "image/gif",
    ".webp": "image/webp",
    ".bmp":  "image/bmp",
    ".tiff": "image/tiff",
    ".tif":  "image/tiff"
}

def get_mime_type(file_name: str) -> str:
    """
    Get the MIME type for a given file name based on its extension.
    Raises ValueError if the extension is not supported.
    """
    ext = os.path.splitext(file_name)[1].lower()
    if ext in EXTENSION_TO_MIME:
        return EXTENSION_TO_MIME[ext]
    raise ValueError(f"Unsupported file extension {ext}: {file_name}")

async def get_doc(analytiq_client, document_id: str, organization_id: str | None = None) -> dict:
    """
    Get a document by its ID within an organization
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id: str
            Document ID
        organization_id: str | None
            Organization ID. If None, will not filter by organization.

    Returns:
        dict
            Document metadata    
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["docs"]
    
    # Build query based on whether organization_id is provided
    query = {"_id": ObjectId(document_id)}
    if organization_id:
        query["organization_id"] = organization_id
    
    return await collection.find_one(query)

async def save_doc(analytiq_client, document: dict) -> str:
    """
    Save a document (organization_id should be included in document)
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document: dict
            Document metadata to save

    Returns:
        str
            Document ID of the saved document
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    
    if "_id" not in document:
        document["_id"] = ObjectId()
    
    if "organization_id" not in document:
        raise ValueError("organization_id is required")
    
    await db.docs.replace_one(
        {
            "_id": document["_id"],
            "organization_id": document["organization_id"]
        },
        document,
        upsert=True
    )
    
    logger.debug(f"Document {document['_id']} has been saved.")

    return str(document["_id"])

async def delete_doc(analytiq_client, document_id: str, organization_id: str):
    """
    Delete a document within an organization
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id: str
            Document ID to delete
        organization_id: str
            Organization ID
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["docs"]
    
    await collection.delete_one({
        "_id": ObjectId(document_id),
        "organization_id": organization_id
    })

    # Delete all LLM results for the document
    await ad.llm.delete_llm_result(analytiq_client, document_id=document_id)

    # Delete all OCR results for the document
    ad.common.delete_ocr_all(analytiq_client, document_id=document_id)

    logger.info(f"Document {document_id} has been deleted with all LLM and OCR results.")


async def list_docs(
    analytiq_client,
    organization_id: str,
    skip: int = 0,
    limit: int = 10,
    tag_ids: list[str] = None,
    name_search: str = None
) -> tuple[list, int]:
    """
    List documents with pagination within an organization
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        organization_id: str
            Organization ID to filter documents by
        skip: int
            Number of documents to skip
        limit: int
            Maximum number of documents to return

    Returns:
        tuple[list, int]
            List of documents and total count
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["docs"]
    
    # Add organization filter
    query = {"organization_id": organization_id}
    if tag_ids:
        query["tag_ids"] = {"$all": tag_ids}
    if name_search:
        # Search in user_file_name (case-insensitive)
        query["user_file_name"] = {"$regex": name_search, "$options": "i"}
    
    total_count = await collection.count_documents(query)
    cursor = collection.find(query).sort("upload_date", -1).skip(skip).limit(limit)
    documents = await cursor.to_list(length=limit)
    return documents, total_count

async def update_doc_state(analytiq_client, document_id: str, state: str):
    """
    Update document state
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id: str
            Document ID
        state: str
            New state
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["docs"]
    
    await collection.update_one(
        {"_id": ObjectId(document_id)},
        {"$set": {
            "state": state,
            "state_updated_at": datetime.now(UTC)
        }}
    )
    
    logger.debug(f"Document {document_id} state updated to {state}")

async def get_doc_tag_ids(analytiq_client, document_id: str) -> list[str]:
    """
    Get a document tag IDs

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id: str
            Document ID

    Returns:
        list[str]
            Document tag IDs
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["docs"]
    elem = await collection.find_one({"_id": ObjectId(document_id)})
    if elem is None:
        return []
    return elem["tag_ids"]

async def get_doc_ids_by_tag_ids(analytiq_client, tag_ids: list[str]) -> list[str]:
    """
    Get document IDs by tag IDs

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        tag_ids: list[str]
            Tag IDs

    Returns:
        list[str]
            Document IDs
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["docs"]
    cursor = collection.find({"tag_ids": {"$in": tag_ids}})
    # Convert cursor to list before processing
    elems = await cursor.to_list(length=None)  # None means no limit
    return [str(elem["_id"]) for elem in elems]

def is_pdf_or_image(mime_type):
    return mime_type in [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/tiff"
    ]