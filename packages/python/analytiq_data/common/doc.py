from datetime import datetime, UTC
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
from typing import Any

import analytiq_data as ad
from analytiq_data.common.tag_grid_filters import resolve_tag_filter_values_to_ids

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
    await ad.ocr.delete_ocr_all(analytiq_client, document_id=document_id)

    # Delete KB vectors and document_index entries for this document
    # Find all KBs this document is indexed in
    index_entries = await db.document_index.find({"document_id": document_id}).to_list(length=None)
    for entry in index_entries:
        kb_id = str(entry["kb_id"])  # Ensure string type for consistency
        try:
            # Remove document from KB (this handles vectors and document_index cleanup)
            await ad.kb.indexing.remove_document_from_kb(
                analytiq_client,
                kb_id,
                document_id,
                organization_id
            )
        except Exception as e:
            logger.warning(f"Error removing document {document_id} from KB {kb_id} during deletion: {e}")
            # Continue with other KBs even if one fails

    logger.info(f"Document {document_id} has been deleted with all LLM, OCR, and KB results.")


async def list_docs(
    analytiq_client,
    organization_id: str,
    skip: int = 0,
    limit: int = 10,
    tag_ids: list[str] = None,
    name_search: str = None,
    metadata_search: dict[str, str] = None,
    sort_model: list[dict[str, Any]] | None = None,
    filter_model: dict[str, Any] | None = None,
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
        tag_ids: list[str], optional
            List of tag IDs to filter by (all tags must be present)
        name_search: str, optional
            Search term for document names (case-insensitive)
        metadata_search: dict[str, str], optional
            Key-value pairs to search in metadata (all pairs must match)
        sort_model: list[dict], optional
            MUI DataGrid sortModel (array).
        filter_model: dict, optional
            MUI DataGrid filterModel (object). Applied in addition to explicit filters.

    Returns:
        tuple[list, int]
            List of documents and total count
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["docs"]
    tags_collection = db["tags"]
    
    # Add organization filter
    query = {"organization_id": organization_id}
    if tag_ids:
        query["tag_ids"] = {"$all": tag_ids}
    if name_search:
        # Search in user_file_name (case-insensitive)
        query["user_file_name"] = {"$regex": name_search, "$options": "i"}
    if metadata_search:
        # Search in metadata key-value pairs (all pairs must match)
        for key, value in metadata_search.items():
            query[f"metadata.{key}"] = value
    # Apply grid-style filters (MUI DataGrid filterModel)
    if filter_model and isinstance(filter_model, dict):
        items = filter_model.get("items") or []
        logic = (filter_model.get("logicOperator") or "and").lower()

        def mongo_field(field: str) -> str | None:
            return {
                "document_name": "user_file_name",
                "uploaded_by": "uploaded_by",
                "state": "state",
                "upload_date": "upload_date",
                "tag_ids": "tag_ids",
            }.get(field)

        def as_list_value(v: Any) -> list[str]:
            if v is None:
                return []
            if isinstance(v, list):
                return [str(x) for x in v if str(x).strip()]
            # DataGrid sometimes passes a comma-separated string
            s = str(v)
            if "," in s:
                return [p.strip() for p in s.split(",") if p.strip()]
            return [s.strip()] if s.strip() else []

        def parse_dt(v: Any) -> datetime | None:
            if v is None:
                return None
            if isinstance(v, datetime):
                return v
            s = str(v).strip()
            if not s:
                return None
            # Accept ISO strings; tolerate trailing Z.
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(s)
            except Exception:
                # If user provides date-only, treat as midnight UTC.
                try:
                    return datetime.fromisoformat(s + "T00:00:00+00:00")
                except Exception:
                    return None

        clauses: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            field = item.get("field")
            op = item.get("operator") or item.get("operatorValue")
            value = item.get("value")
            if not field or not op:
                continue

            mf = mongo_field(str(field))
            if not mf:
                continue

            op = str(op)
            str_value = "" if value is None else str(value)

            if op in ("isEmpty", "is empty"):
                clauses.append({"$or": [{mf: ""}, {mf: None}, {mf: {"$exists": False}}]})
                continue
            if op in ("isNotEmpty", "is not empty"):
                clauses.append({"$and": [{mf: {"$exists": True}}, {mf: {"$nin": ["", None]}}]})
                continue

            if op in ("isAnyOf", "is any of"):
                values = as_list_value(value)
                if not values:
                    continue
                if mf == "tag_ids":
                    tag_id_strs = await resolve_tag_filter_values_to_ids(db, organization_id, values)
                    if not tag_id_strs:
                        clauses.append({"_id": {"$exists": False}})
                        continue
                    clauses.append({mf: {"$in": tag_id_strs}})
                else:
                    clauses.append({mf: {"$in": values}})
                continue

            if mf == "upload_date":
                dt = parse_dt(value)
                if op in ("is", "equals") and dt:
                    clauses.append({mf: dt})
                elif op in ("not", "doesNotEqual", "does not equal") and dt:
                    clauses.append({mf: {"$ne": dt}})
                elif op in ("after",) and dt:
                    clauses.append({mf: {"$gt": dt}})
                elif op in ("onOrAfter", "on or after") and dt:
                    clauses.append({mf: {"$gte": dt}})
                elif op in ("before",) and dt:
                    clauses.append({mf: {"$lt": dt}})
                elif op in ("onOrBefore", "on or before") and dt:
                    clauses.append({mf: {"$lte": dt}})
                elif op in ("isEmpty", "is empty"):
                    clauses.append({"$or": [{mf: None}, {mf: {"$exists": False}}]})
                elif op in ("isNotEmpty", "is not empty"):
                    clauses.append({mf: {"$and": [{mf: {"$exists": True}}, {mf: {"$ne": None}}]}})
                continue

            # Tag operators beyond "isAnyOf": treat scalar value as "any-of-one".
            if mf == "tag_ids" and str_value.strip():
                # Grid UI provides text operators, but docs store tag IDs not tag names.
                # Interpret these operators as tag *name* search scoped to the org, then
                # filter documents by the matching tag IDs.
                name_query: dict[str, Any] | None = None
                if op == "contains":
                    name_query = {"$regex": re.escape(str_value), "$options": "i"}
                elif op in ("startsWith", "starts with"):
                    name_query = {"$regex": f"^{re.escape(str_value)}", "$options": "i"}
                elif op in ("endsWith", "ends with"):
                    name_query = {"$regex": f"{re.escape(str_value)}$", "$options": "i"}
                elif op in ("equals", "=", "is"):
                    name_query = {"$regex": f"^{re.escape(str_value)}$", "$options": "i"}
                elif op in ("doesNotContain", "does not contain"):
                    name_query = {"$regex": re.escape(str_value), "$options": "i"}
                elif op in ("doesNotEqual", "does not equal"):
                    name_query = str_value

                if name_query is not None:
                    # Cap results to avoid runaway $in lists.
                    tag_docs = await tags_collection.find(
                        {"organization_id": organization_id, "name": name_query},
                        {"_id": 1},
                    ).limit(200).to_list(length=200)
                    tag_id_strs = [str(t["_id"]) for t in tag_docs]
                    if not tag_id_strs:
                        # No matching tags => contains/equals yields no docs; negations yield all docs.
                        if op in ("doesNotContain", "does not contain", "doesNotEqual", "does not equal"):
                            continue
                        clauses.append({"_id": {"$exists": False}})
                        continue

                    if op in ("doesNotContain", "does not contain", "doesNotEqual", "does not equal"):
                        clauses.append({mf: {"$nin": tag_id_strs}})
                    else:
                        clauses.append({mf: {"$in": tag_id_strs}})
                    continue

            # String-ish operators
            if op in ("contains",):
                if not str_value.strip():
                    continue
                clauses.append({mf: {"$regex": re.escape(str_value), "$options": "i"}})
                continue
            if op in ("doesNotContain", "does not contain"):
                if not str_value.strip():
                    continue
                clauses.append({mf: {"$not": {"$regex": re.escape(str_value), "$options": "i"}}})
                continue
            if op in ("equals",):
                clauses.append({mf: str_value})
                continue
            if op in ("doesNotEqual", "does not equal"):
                clauses.append({mf: {"$ne": str_value}})
                continue
            if op in ("startsWith", "starts with"):
                if not str_value.strip():
                    continue
                clauses.append({mf: {"$regex": f"^{re.escape(str_value)}", "$options": "i"}})
                continue
            if op in ("endsWith", "ends with"):
                if not str_value.strip():
                    continue
                clauses.append({mf: {"$regex": f"{re.escape(str_value)}$", "$options": "i"}})
                continue

        if clauses:
            if logic == "or":
                query = {"$and": [query, {"$or": clauses}]}
            else:
                query = {"$and": [query, *clauses]}
    
    total_count = await collection.count_documents(query)

    def map_sort_field(field: str | None) -> str:
        return {
            None: "upload_date",
            "upload_date": "upload_date",
            "uploadDate": "upload_date",
            "document_name": "user_file_name",
            "documentName": "user_file_name",
            "uploaded_by": "uploaded_by",
            "uploadedBy": "uploaded_by",
            "state": "state",
        }.get(field, "upload_date")

    sort_spec: list[tuple[str, int]] = []
    if sort_model and isinstance(sort_model, list):
        for s in sort_model:
            if not isinstance(s, dict):
                continue
            field = map_sort_field(s.get("field"))
            direction = 1 if str(s.get("sort", "")).lower() == "asc" else -1
            sort_spec.append((field, direction))

    # Stable ordering: always tie-break by upload_date desc.
    if not any(f == "upload_date" for f, _ in sort_spec):
        sort_spec.append(("upload_date", -1))

    cursor = collection.find(query).sort(sort_spec).skip(skip).limit(limit)
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

def ocr_supported(file_name: str) -> bool:
    """Check if OCR is supported for a file based on its extension"""
    if not file_name:
        return False
    ext = os.path.splitext(file_name)[1].lower()
    # OCR not supported for structured data files
    skip_extensions = {'.csv', '.xls', '.xlsx', '.txt', '.md'}
    return ext not in skip_extensions