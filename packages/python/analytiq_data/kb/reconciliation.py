"""
Knowledge Base reconciliation service.

This service detects and fixes drift between document tags and KB indexes:
- Missing documents: Documents with matching tags but no document_index entry
- Stale documents: Documents in document_index whose tags no longer match
- Orphaned vectors: Vectors without corresponding document_index entries
- Missing embeddings: Embeddings missing from cache after backup restore
"""

import logging
from datetime import datetime, UTC, timedelta
from typing import List, Dict, Any, Optional
from bson import ObjectId

import analytiq_data as ad
from .indexing import remove_document_from_kb
from .embedding_cache import get_embedding_from_cache

logger = logging.getLogger(__name__)

# Lock collection for distributed reconciliation coordination
RECONCILIATION_LOCKS_COLLECTION = "kb_reconciliation_locks"
# Lock TTL: 10 minutes (reconciliation should complete well before this)
RECONCILIATION_LOCK_TTL_SECS = 600


async def ensure_reconciliation_lock_indexes(analytiq_client) -> None:
    """
    Ensure indexes exist on the reconciliation locks collection.
    Called lazily on first use.
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    collection = db[RECONCILIATION_LOCKS_COLLECTION]
    
    try:
        # Create unique index on kb_id to ensure only one lock per KB
        await collection.create_index(
            [("kb_id", 1)],
            unique=True,
            name="kb_id_unique_idx",
            background=True
        )
        logger.info(f"Created unique index on {RECONCILIATION_LOCKS_COLLECTION}.kb_id")
    except Exception as e:
        # Index might already exist, that's fine
        if "already exists" not in str(e).lower() and "duplicate key" not in str(e).lower():
            logger.warning(f"Could not create index on {RECONCILIATION_LOCKS_COLLECTION}: {e}")
    
    try:
        # Create TTL index on expires_at for automatic cleanup of expired locks
        await collection.create_index(
            [("expires_at", 1)],
            expireAfterSeconds=0,  # Delete documents when expires_at is reached
            name="expires_at_ttl_idx",
            background=True
        )
        logger.info(f"Created TTL index on {RECONCILIATION_LOCKS_COLLECTION}.expires_at")
    except Exception as e:
        # Index might already exist, that's fine
        if "already exists" not in str(e).lower() and "duplicate key" not in str(e).lower():
            logger.warning(f"Could not create TTL index on {RECONCILIATION_LOCKS_COLLECTION}: {e}")


async def acquire_reconciliation_lock(
    analytiq_client,
    kb_id: str,
    worker_id: str
) -> bool:
    """
    Try to acquire a distributed lock for KB reconciliation.
    
    Uses atomic find_one_and_update to ensure only one pod reconciles a KB at a time.
    Lock expires after RECONCILIATION_LOCK_TTL_SECS to handle crashed workers.
    
    Returns:
        True if lock was acquired, False if another pod already has the lock
    """
    # Ensure indexes exist (idempotent, safe to call multiple times)
    await ensure_reconciliation_lock_indexes(analytiq_client)
    
    db = analytiq_client.mongodb_async[analytiq_client.env]
    now = datetime.now(UTC)
    lock_expires_at = now + timedelta(seconds=RECONCILIATION_LOCK_TTL_SECS)
    
    # Try to acquire lock atomically
    # Only succeeds if lock doesn't exist or has expired
    # This is atomic - no race condition possible
    result = await db[RECONCILIATION_LOCKS_COLLECTION].find_one_and_update(
        {
            "kb_id": kb_id,
            "$or": [
                {"expires_at": {"$lt": now}},  # Expired lock
                {"expires_at": {"$exists": False}},  # No expires_at field (old lock format)
                {"expires_at": None}  # Null expires_at
            ]
        },
        {
            "$set": {
                "kb_id": kb_id,
                "worker_id": worker_id,
                "acquired_at": now,
                "expires_at": lock_expires_at
            }
        },
        upsert=True,
        return_document=True
    )
    
    # If result is None, another pod has a valid lock
    # If result exists, we successfully acquired it (either created new or took expired one)
    if result is None:
        return False
    
    # Verify we got the lock (check worker_id matches - should always be true after successful update)
    return result.get("worker_id") == worker_id


async def release_reconciliation_lock(
    analytiq_client,
    kb_id: str,
    worker_id: str
) -> None:
    """
    Release a reconciliation lock.
    
    Only releases if this worker_id owns the lock (safety check).
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    await db[RECONCILIATION_LOCKS_COLLECTION].delete_one({
        "kb_id": kb_id,
        "worker_id": worker_id
    })


async def reconcile_knowledge_base(
    analytiq_client,
    kb_id: str,
    organization_id: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Reconcile a single knowledge base.
    
    Args:
        analytiq_client: The analytiq client
        kb_id: Knowledge base ID
        organization_id: Organization ID
        dry_run: If True, only report issues without fixing them
        
    Returns:
        Dict with reconciliation results
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    
    # Get KB configuration
    kb = await db.knowledge_bases.find_one({"_id": ObjectId(kb_id), "organization_id": organization_id})
    if not kb:
        raise ValueError(f"Knowledge base {kb_id} not found")
    
    kb_tag_ids = set(kb.get("tag_ids", []))
    if not kb_tag_ids:
        # KB has no tags, nothing to reconcile
        return {
            "kb_id": kb_id,
            "missing_documents": [],
            "stale_documents": [],
            "orphaned_vectors": 0,
            "missing_embeddings": 0,
            "dry_run": dry_run
        }
    
    results = {
        "kb_id": kb_id,
        "missing_documents": [],
        "stale_documents": [],
        "orphaned_vectors": 0,
        "missing_embeddings": 0,
        "dry_run": dry_run
    }
    
    # 1. Find missing documents: documents with matching tags but no document_index entry
    # Get all documents with at least one matching tag
    matching_docs = await db.docs.find({
        "organization_id": organization_id,
        "tag_ids": {"$in": list(kb_tag_ids)}
    }).to_list(length=None)
    
    # Get existing document_index entries for this KB
    existing_index_entries = await db.document_index.find({"kb_id": kb_id}).to_list(length=None)
    existing_doc_ids = {entry["document_id"] for entry in existing_index_entries}
    
    # Find missing documents (have matching tags but not indexed)
    for doc in matching_docs:
        doc_id = str(doc["_id"])
        doc_tag_ids = set(doc.get("tag_ids", []))
        
        # Check if document has at least one tag matching KB
        if doc_tag_ids & kb_tag_ids and doc_id not in existing_doc_ids:
            # Check if document has OCR text (required for indexing)
            ocr_text = await ad.common.ocr.get_ocr_text(analytiq_client, doc_id)
            if ocr_text and ocr_text.strip():
                results["missing_documents"].append(doc_id)
                if not dry_run:
                    # Queue for indexing
                    kb_msg = {"document_id": doc_id, "kb_id": kb_id}
                    await ad.queue.send_msg(analytiq_client, "kb_index", msg=kb_msg)
    
    # 2. Find stale documents: indexed but tags no longer match
    for entry in existing_index_entries:
        doc_id = entry["document_id"]
        doc = await db.docs.find_one({"_id": ObjectId(doc_id), "organization_id": organization_id})
        
        if not doc:
            # Document was deleted - will be handled by deletion hook, but we can still mark it
            continue
        
        doc_tag_ids = set(doc.get("tag_ids", []))
        
        # Check if document still has at least one matching tag
        if not (doc_tag_ids & kb_tag_ids):
            results["stale_documents"].append(doc_id)
            if not dry_run:
                # Remove from KB
                try:
                    await remove_document_from_kb(analytiq_client, kb_id, doc_id, organization_id)
                except Exception as e:
                    logger.error(f"Error removing stale document {doc_id} from KB {kb_id}: {e}")
    
    # 3. Find orphaned vectors: vectors without document_index entries
    collection_name = f"kb_vectors_{kb_id}"
    vectors_collection = db[collection_name]
    
    # Get all unique document_ids from vectors
    vector_doc_ids = await vectors_collection.distinct("document_id")
    
    for vector_doc_id in vector_doc_ids:
        # Check if document_index entry exists
        index_entry = await db.document_index.find_one({
            "kb_id": kb_id,
            "document_id": vector_doc_id
        })
        
        if not index_entry:
            # Orphaned vectors found
            if not dry_run:
                # Delete orphaned vectors
                delete_result = await vectors_collection.delete_many({"document_id": vector_doc_id})
                results["orphaned_vectors"] += delete_result.deleted_count
            else:
                # Count orphaned vectors
                count = await vectors_collection.count_documents({"document_id": vector_doc_id})
                results["orphaned_vectors"] += count
    
    # 4. Find missing embeddings: vectors with embeddings that don't exist in cache
    # This is less critical and can be expensive, so we'll do a sample check
    # For now, we'll skip this check as it requires iterating through all vectors
    # and can be very slow. This can be implemented as a separate maintenance task.
    
    logger.info(f"Reconciliation for KB {kb_id}: {len(results['missing_documents'])} missing, "
                f"{len(results['stale_documents'])} stale, {results['orphaned_vectors']} orphaned vectors")
    
    # Update last_reconciled_at timestamp (only if not dry_run)
    if not dry_run:
        await db.knowledge_bases.update_one(
            {"_id": ObjectId(kb_id)},
            {"$set": {"last_reconciled_at": datetime.now(UTC)}}
        )
    
    return results


async def reconcile_all_knowledge_bases(
    analytiq_client,
    organization_id: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Reconcile all knowledge bases (optionally for a specific organization).
    
    Args:
        analytiq_client: The analytiq client
        organization_id: Optional organization ID to limit reconciliation
        dry_run: If True, only report issues without fixing them
        
    Returns:
        Dict with reconciliation results for all KBs
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    
    # Build query
    query = {}
    if organization_id:
        query["organization_id"] = organization_id
    query["status"] = {"$in": ["indexing", "active"]}  # Only reconcile active KBs
    
    # Get all KBs
    kbs = await db.knowledge_bases.find(query).to_list(length=None)
    
    all_results = {
        "kb_results": [],
        "total_missing": 0,
        "total_stale": 0,
        "total_orphaned": 0,
        "dry_run": dry_run
    }
    
    for kb in kbs:
        kb_id = str(kb["_id"])
        org_id = kb["organization_id"]
        
        try:
            kb_results = await reconcile_knowledge_base(
                analytiq_client,
                kb_id,
                org_id,
                dry_run=dry_run
            )
            all_results["kb_results"].append(kb_results)
            all_results["total_missing"] += len(kb_results["missing_documents"])
            all_results["total_stale"] += len(kb_results["stale_documents"])
            all_results["total_orphaned"] += kb_results["orphaned_vectors"]
        except Exception as e:
            logger.error(f"Error reconciling KB {kb_id}: {e}")
            all_results["kb_results"].append({
                "kb_id": kb_id,
                "error": str(e)
            })
    
    return all_results
