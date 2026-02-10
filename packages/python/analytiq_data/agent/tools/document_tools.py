"""
Document tools for the agent: list, update, and delete documents.
Same semantics as MCP list_documents, update_document, delete_document.
"""
from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Any

from bson import ObjectId

import analytiq_data as ad

logger = logging.getLogger(__name__)


def _db(context: dict):
    return ad.common.get_async_db(context["analytiq_client"])


def _is_valid_object_id(s: str) -> bool:
    return len(s) == 24 and all(c in "0123456789abcdef" for c in s.lower())


def _doc_to_serializable(doc: dict) -> dict:
    """Convert a doc from DB to JSON-friendly dict (id, document_name, tag_ids, metadata, etc.)."""
    upload_date = doc.get("upload_date")
    if isinstance(upload_date, datetime):
        upload_date = upload_date.replace(tzinfo=UTC).isoformat()
    return {
        "id": str(doc["_id"]),
        "document_name": doc.get("user_file_name", doc.get("document_name", "")),
        "upload_date": upload_date,
        "uploaded_by": doc.get("uploaded_by", ""),
        "state": doc.get("state", ""),
        "tag_ids": doc.get("tag_ids", []),
        "metadata": doc.get("metadata", {}),
    }


async def list_documents(context: dict, params: dict) -> dict[str, Any]:
    """
    List documents in the organization with optional filters.
    Same as MCP list_documents.
    """
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    skip = int(params.get("skip", 0))
    limit = int(params.get("limit", 10))
    limit = min(max(limit, 1), 100)
    name_search = params.get("name_search")
    tag_ids = params.get("tag_ids")
    if isinstance(tag_ids, str):
        tag_ids = [t.strip() for t in tag_ids.split(",")] if tag_ids else None
    metadata_search = params.get("metadata_search")
    if isinstance(metadata_search, str):
        metadata_search = {}
        for pair in metadata_search.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                metadata_search[k.strip()] = v.strip()
    elif not isinstance(metadata_search, dict):
        metadata_search = None

    docs, total_count = await ad.common.list_docs(
        context["analytiq_client"],
        organization_id=org_id,
        skip=skip,
        limit=limit,
        tag_ids=tag_ids,
        name_search=name_search,
        metadata_search=metadata_search,
    )
    return {
        "documents": [_doc_to_serializable(d) for d in docs],
        "total_count": total_count,
        "skip": skip,
    }


async def delete_document(context: dict, params: dict) -> dict[str, Any]:
    """
    Delete a document and its files. Same as MCP delete_document.
    document_id defaults to the current document in context.
    """
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    document_id = params.get("document_id") or context.get("document_id")
    if not document_id:
        return {"error": "document_id is required (or use current document context)"}
    if not _is_valid_object_id(document_id):
        return {"error": "document_id must be a valid 24-character hex ID"}

    db = _db(context)
    document = await db.docs.find_one(
        {"_id": ObjectId(document_id), "organization_id": org_id}
    )
    if not document:
        return {"error": "Document not found"}
    if "mongo_file_name" not in document:
        return {"error": "Document metadata is corrupted: missing mongo_file_name"}

    await ad.common.delete_file_async(
        context["analytiq_client"], file_name=document["mongo_file_name"]
    )
    pdf_file_name = document.get("pdf_file_name")
    if pdf_file_name and pdf_file_name != document["mongo_file_name"]:
        await ad.common.delete_file_async(
            context["analytiq_client"], file_name=pdf_file_name
        )
    await ad.common.delete_doc(context["analytiq_client"], document_id, org_id)
    logger.info("Deleted document %s", document_id)
    return {"message": "Document deleted successfully", "document_id": document_id}


async def update_document(context: dict, params: dict) -> dict[str, Any]:
    """
    Update document metadata: name, tag_ids, and/or metadata.
    Same as MCP update_document. document_id defaults to the current document in context.
    """
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    document_id = params.get("document_id") or context.get("document_id")
    if not document_id:
        return {"error": "document_id is required (or use current document context)"}
    if not _is_valid_object_id(document_id):
        return {"error": "document_id must be a valid 24-character hex ID"}

    document_name = params.get("document_name")
    tag_ids = params.get("tag_ids")
    metadata = params.get("metadata")

    db = _db(context)
    document = await db.docs.find_one(
        {"_id": ObjectId(document_id), "organization_id": org_id}
    )
    if not document:
        return {"error": "Document not found"}

    if tag_ids is not None:
        if not isinstance(tag_ids, list):
            tag_ids = [str(t) for t in (tag_ids if isinstance(tag_ids, str) else [])]
        else:
            tag_ids = [str(t) for t in tag_ids]
        invalid_format = [tid for tid in tag_ids if not _is_valid_object_id(tid)]
        if invalid_format:
            return {"error": f"Invalid tag ID format (must be 24-char hex): {invalid_format}"}
        tags_cursor = db.tags.find(
            {"_id": {"$in": [ObjectId(tid) for tid in tag_ids]}, "organization_id": org_id}
        )
        existing_tags = await tags_cursor.to_list(None)
        existing_tag_ids = {str(t["_id"]) for t in existing_tags}
        invalid = set(tag_ids) - existing_tag_ids
        if invalid:
            return {"error": f"Invalid tag IDs: {list(invalid)}"}

    update_dict = {}
    if document_name is not None:
        update_dict["user_file_name"] = document_name
    if tag_ids is not None:
        update_dict["tag_ids"] = tag_ids
    if metadata is not None:
        if not isinstance(metadata, dict):
            return {"error": "metadata must be an object (key-value pairs)"}
        update_dict["metadata"] = {str(k): str(v) for k, v in metadata.items()}

    if not update_dict:
        return {"message": "No updates provided", "document_id": document_id}

    old_tag_ids = document.get("tag_ids", [])
    updated = await db.docs.find_one_and_update(
        {"_id": ObjectId(document_id), "organization_id": org_id},
        {"$set": update_dict},
        return_document=True,
    )
    if not updated:
        return {"error": "Document not found"}

    # If tags changed, queue KB re-index and reconcile (same as documents route)
    if tag_ids is not None:
        new_set = set(tag_ids)
        old_set = set(old_tag_ids)
        if new_set != old_set:
            await ad.queue.send_msg(context["analytiq_client"], "kb_index", msg={"document_id": document_id})
            logger.info("Queued KB indexing for document %s due to tag changes", document_id)
            if old_set - new_set:
                try:
                    await ad.kb.reconciliation.reconcile_knowledge_base(
                        analytiq_client=context["analytiq_client"],
                        organization_id=org_id,
                        doc_id=document_id,
                        dry_run=False,
                    )
                    logger.info("Auto-reconciled document %s after tag removal", document_id)
                except Exception as e:
                    logger.error("Error auto-reconciling document %s: %s", document_id, e)

    return {
        "message": "Document updated successfully",
        "document_id": document_id,
        "document_name": updated.get("user_file_name"),
        "tag_ids": updated.get("tag_ids", []),
        "metadata": updated.get("metadata", {}),
    }
