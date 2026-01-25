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
    organization_id: str,
    kb_id: Optional[str] = None,
    doc_id: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Reconcile knowledge base(s) and/or document(s).
    
    Args:
        analytiq_client: The analytiq client
        organization_id: Organization ID
        kb_id: Optional knowledge base ID. If provided, only reconcile this KB.
        doc_id: Optional document ID. If provided, only check this document across KBs.
        dry_run: If True, only report issues without fixing them
        
    Returns:
        Dict with reconciliation results. If doc_id is provided, returns results for all affected KBs.
        If kb_id is provided, returns results for that KB.
        
    Note:
        - If both kb_id and doc_id are provided, checks that document in that KB only
        - If only doc_id is provided, checks that document across all KBs in the organization
        - If only kb_id is provided, performs full KB reconciliation (default behavior)
        - If neither is provided, raises ValueError
    """
    if not kb_id and not doc_id:
        raise ValueError("Either kb_id or doc_id (or both) must be provided")
    
    db = analytiq_client.mongodb_async[analytiq_client.env]
    
    # If doc_id is provided, reconcile that document
    if doc_id:
        return await _reconcile_document(analytiq_client, organization_id, doc_id, kb_id, dry_run)
    
    # Otherwise, reconcile the KB (full reconciliation)
    if not kb_id:
        raise ValueError("kb_id must be provided when doc_id is not provided")
    
    return await _reconcile_kb_full(analytiq_client, organization_id, kb_id, dry_run)


async def _reconcile_document(
    analytiq_client,
    organization_id: str,
    doc_id: str,
    kb_id: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Reconcile a specific document across KBs (or in a specific KB if kb_id is provided).
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    
    # Get the document
    doc = await db.docs.find_one({"_id": ObjectId(doc_id), "organization_id": organization_id})
    if not doc:
        raise ValueError(f"Document {doc_id} not found")
    
    doc_tag_ids = set(doc.get("tag_ids", []))
    
    # Find KBs to check
    if kb_id:
        # Check only in the specified KB
        kb = await db.knowledge_bases.find_one({"_id": ObjectId(kb_id), "organization_id": organization_id})
        if not kb:
            raise ValueError(f"Knowledge base {kb_id} not found")
        kbs_to_check = [kb]
    else:
        # Check in all KBs that match the document's tags (or all KBs if doc has no tags)
        if doc_tag_ids:
            kbs_to_check = await db.knowledge_bases.find({
                "organization_id": organization_id,
                "status": {"$in": ["indexing", "active"]},
                "tag_ids": {"$in": list(doc_tag_ids)}
            }).to_list(length=None)
        else:
            # Document has no tags - check all KBs where it might be indexed
            existing_index_entries = await db.document_index.find({"document_id": doc_id}).to_list(length=None)
            existing_kb_ids = {entry["kb_id"] for entry in existing_index_entries}
            if existing_kb_ids:
                kbs_to_check = await db.knowledge_bases.find({
                    "_id": {"$in": [ObjectId(kb_id) for kb_id in existing_kb_ids]},
                    "organization_id": organization_id,
                    "status": {"$in": ["indexing", "active"]}
                }).to_list(length=None)
            else:
                kbs_to_check = []
    
    all_results = {
        "doc_id": doc_id,
        "kb_results": [],
        "total_missing": 0,
        "total_stale": 0,
        "total_orphaned": 0,
        "dry_run": dry_run
    }
    
    for kb in kbs_to_check:
        kb_id_str = str(kb["_id"])
        kb_tag_ids = set(kb.get("tag_ids", []))
        
        kb_result = {
            "kb_id": kb_id_str,
            "missing_documents": [],
            "stale_documents": [],
            "orphaned_vectors": 0,
            "missing_embeddings": 0,
            "dry_run": dry_run
        }
        
        # Check if document should be in this KB
        should_be_indexed = bool(doc_tag_ids & kb_tag_ids) if kb_tag_ids else False
        
        # Check if document is indexed in this KB
        index_entry = await db.document_index.find_one({
            "kb_id": kb_id_str,
            "document_id": doc_id
        })
        is_indexed = index_entry is not None
        
        if should_be_indexed and not is_indexed:
            # Document should be indexed but isn't
            kb_result["missing_documents"].append(doc_id)
            if not dry_run:
                # Check if document has OCR text (required for indexing)
                ocr_text = await ad.common.ocr.get_ocr_text(analytiq_client, doc_id)
                if ocr_text and ocr_text.strip():
                    kb_msg = {"document_id": doc_id, "kb_id": kb_id_str}
                    await ad.queue.send_msg(analytiq_client, "kb_index", msg=kb_msg)
        elif not should_be_indexed and is_indexed:
            # Document is indexed but shouldn't be (stale)
            kb_result["stale_documents"].append(doc_id)
            if not dry_run:
                try:
                    await remove_document_from_kb(analytiq_client, kb_id_str, doc_id, organization_id)
                except Exception as e:
                    logger.error(f"Error removing stale document {doc_id} from KB {kb_id_str}: {e}")
        
        # Check for orphaned vectors for this document
        collection_name = f"kb_vectors_{kb_id_str}"
        vectors_collection = db[collection_name]
        if is_indexed:
            # Check if vectors exist but index entry doesn't (shouldn't happen, but check anyway)
            vector_count = await vectors_collection.count_documents({"document_id": doc_id})
            if vector_count > 0 and not index_entry:
                kb_result["orphaned_vectors"] = vector_count
                if not dry_run:
                    await vectors_collection.delete_many({"document_id": doc_id})
        else:
            # Document not indexed - check if there are orphaned vectors
            vector_count = await vectors_collection.count_documents({"document_id": doc_id})
            if vector_count > 0:
                kb_result["orphaned_vectors"] = vector_count
                if not dry_run:
                    await vectors_collection.delete_many({"document_id": doc_id})
        
        all_results["kb_results"].append(kb_result)
        all_results["total_missing"] += len(kb_result["missing_documents"])
        all_results["total_stale"] += len(kb_result["stale_documents"])
        all_results["total_orphaned"] += kb_result["orphaned_vectors"]
    
    # Update last_reconciled_at for affected KBs (only if not dry_run)
    if not dry_run:
        for kb in kbs_to_check:
            kb_id_str = str(kb["_id"])
            await db.knowledge_bases.update_one(
                {"_id": ObjectId(kb_id_str)},
                {"$set": {"last_reconciled_at": datetime.now(UTC)}}
            )
    
    return all_results


async def _reconcile_kb_full(
    analytiq_client,
    organization_id: str,
    kb_id: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Perform full reconciliation of a knowledge base (original behavior).
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
    
    # Batch size for processing documents (to handle large workspaces)
    BATCH_SIZE = 100
    
    # 1. Find missing documents: documents with matching tags but no document_index entry
    # Process documents in batches to avoid loading all into memory
    logger.info(f"Reconciling KB {kb_id}: Checking for missing documents (processing in batches of {BATCH_SIZE})")
    
    # First, get all existing document_index entries for this KB (we need this set for comparison)
    # This is typically much smaller than all documents, so loading it is acceptable
    existing_index_entries = await db.document_index.find({"kb_id": kb_id}).to_list(length=None)
    existing_doc_ids = {entry["document_id"] for entry in existing_index_entries}
    
    # Process matching documents in batches
    skip = 0
    while True:
        matching_docs = await db.docs.find({
            "organization_id": organization_id,
            "tag_ids": {"$in": list(kb_tag_ids)}
        }).skip(skip).limit(BATCH_SIZE).to_list(length=BATCH_SIZE)
        
        if not matching_docs:
            break
        
        # Find missing documents in this batch
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
        
        # If we got fewer documents than the batch size, we've reached the end
        if len(matching_docs) < BATCH_SIZE:
            break
        
        skip += BATCH_SIZE
    
    # 2. Find stale documents: indexed but tags no longer match
    # Process existing_index_entries in batches
    logger.info(f"Reconciling KB {kb_id}: Checking for stale documents (processing {len(existing_index_entries)} entries in batches)")
    
    for i in range(0, len(existing_index_entries), BATCH_SIZE):
        batch = existing_index_entries[i:i + BATCH_SIZE]
        
        for entry in batch:
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
    # Process in batches to avoid loading all vector document IDs into memory
    logger.info(f"Reconciling KB {kb_id}: Checking for orphaned vectors (processing in batches)")
    collection_name = f"kb_vectors_{kb_id}"
    vectors_collection = db[collection_name]
    
    # Get all unique document_ids from vectors using distinct (this is efficient)
    # But process them in batches to avoid memory issues
    vector_doc_ids = await vectors_collection.distinct("document_id")
    
    # Process vector document IDs in batches
    for i in range(0, len(vector_doc_ids), BATCH_SIZE):
        batch = vector_doc_ids[i:i + BATCH_SIZE]
        
        for vector_doc_id in batch:
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
                organization_id=org_id,
                kb_id=kb_id,
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
