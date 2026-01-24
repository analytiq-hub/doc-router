"""
Message handler for Knowledge Base indexing jobs.
"""

import logging
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.kb.indexing import index_document_in_kb, remove_document_from_kb
from analytiq_data.kb.errors import is_permanent_embedding_error, set_kb_status_to_error

logger = logging.getLogger(__name__)


async def process_kb_index_msg(analytiq_client, msg, force: bool = False):
    """
    Process a KB indexing message.
    
    Message format:
    {
        "document_id": str,
        "kb_id": str,  # Optional - if not provided, will index into all matching KBs
        "action": "index" | "remove"  # Optional, default: "index"
    }
    
    Args:
        analytiq_client: The analytiq client
        msg: The queue message
        force: Whether to force re-indexing (ignored for now)
    """
    logger.info(f"Processing KB index msg: {msg}")
    
    msg_id = msg["_id"]
    document_id = None
    kb_id = None
    action = "index"
    
    try:
        msg_body = msg.get("msg", {})
        document_id = msg_body.get("document_id")
        kb_id = msg_body.get("kb_id")  # Optional
        action = msg_body.get("action", "index")  # "index" or "remove"
        
        if not document_id:
            logger.error("KB index message missing document_id")
            return
        
        # Get document to find organization_id
        doc = await ad.common.doc.get_doc(analytiq_client, document_id)
        if not doc:
            logger.error(f"Document {document_id} not found. Skipping KB indexing.")
            return
        
        organization_id = doc.get("organization_id")
        if not organization_id:
            logger.error(f"Document {document_id} missing organization_id. Skipping KB indexing.")
            return
        
        if action == "remove":
            # Remove document from specific KB or all KBs
            if kb_id:
                await remove_document_from_kb(analytiq_client, kb_id, document_id, organization_id)
            else:
                # Remove from all KBs (find all KBs this document is in)
                db = analytiq_client.mongodb_async[analytiq_client.env]
                index_entries = await db.document_index.find({"document_id": document_id}).to_list(length=None)
                for entry in index_entries:
                    await remove_document_from_kb(
                        analytiq_client,
                        entry["kb_id"],
                        document_id,
                        organization_id
                    )
        else:
            # Index document
            if kb_id:
                # Index into specific KB
                try:
                    await index_document_in_kb(analytiq_client, kb_id, document_id, organization_id)
                except Exception as e:
                    # Error handling (including setting KB status to error) is done in index_document_in_kb
                    # Re-raise to mark message as failed
                    raise
            else:
                # Find all KBs that match this document's tags
                doc_tag_ids = await ad.common.doc.get_doc_tag_ids(analytiq_client, document_id)
                
                db = analytiq_client.mongodb_async[analytiq_client.env]
                
                # Get all KBs the document is currently indexed in
                existing_index_entries = await db.document_index.find({"document_id": document_id}).to_list(length=None)
                existing_kb_ids = {entry["kb_id"] for entry in existing_index_entries}
                
                if not doc_tag_ids:
                    # Document has no tags - remove from all KBs
                    logger.info(f"Document {document_id} has no tags. Removing from all KBs.")
                    for kb_id in existing_kb_ids:
                        try:
                            await remove_document_from_kb(analytiq_client, kb_id, document_id, organization_id)
                        except Exception as e:
                            logger.error(f"Error removing document {document_id} from KB {kb_id}: {e}")
                    return
                
                # Find KBs that match any of the document's tags
                matching_kbs = await db.knowledge_bases.find({
                    "organization_id": organization_id,
                    "status": {"$in": ["indexing", "active"]},  # Only index into active KBs
                    "tag_ids": {"$in": doc_tag_ids}  # KB must have at least one matching tag
                }).to_list(length=None)
                
                matching_kb_ids = {str(kb["_id"]) for kb in matching_kbs}
                
                # Remove from KBs where tags no longer match
                kb_ids_to_remove = existing_kb_ids - matching_kb_ids
                for kb_id in kb_ids_to_remove:
                    try:
                        await remove_document_from_kb(analytiq_client, kb_id, document_id, organization_id)
                        logger.info(f"Removed document {document_id} from KB {kb_id} due to tag mismatch")
                    except Exception as e:
                        logger.error(f"Error removing document {document_id} from KB {kb_id}: {e}")
                
                if not matching_kbs:
                    logger.info(f"No matching KBs found for document {document_id} with tags {doc_tag_ids}")
                    return
                
                # Index into all matching KBs (will re-index if already indexed, which is fine)
                for kb in matching_kbs:
                    try:
                        await index_document_in_kb(
                            analytiq_client,
                            str(kb["_id"]),
                            document_id,
                            organization_id
                        )
                    except Exception as e:
                        logger.error(f"Error indexing document {document_id} into KB {kb['_id']}: {e}")
                        # Check if this is a permanent error that should set KB status to error
                        if is_permanent_embedding_error(e):
                            error_msg = f"Permanent error indexing document {document_id}: {str(e)}"
                            try:
                                await set_kb_status_to_error(
                                    analytiq_client,
                                    str(kb["_id"]),
                                    organization_id,
                                    error_msg
                                )
                            except Exception as status_error:
                                logger.error(f"Failed to set KB {kb['_id']} status to error: {status_error}")
                        # Continue with other KBs even if one fails
        
        logger.info(f"KB indexing completed for document {document_id}")
        
    except Exception as e:
        logger.error(f"Error processing KB index message {msg_id}: {e}")
        # Mark message as failed
        try:
            await ad.queue.delete_msg(analytiq_client, "kb_index", str(msg_id), status="failed")
        except Exception:
            pass
        raise
    
    # Delete the message from the queue
    await ad.queue.delete_msg(analytiq_client, "kb_index", str(msg_id), status="completed")
