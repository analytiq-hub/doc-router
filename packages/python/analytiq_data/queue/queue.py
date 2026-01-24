from datetime import datetime, UTC
from typing import Optional, Dict, Any
from bson import ObjectId
import logging

import analytiq_data as ad

logger = logging.getLogger(__name__)

def get_queue_collection_name(queue_name: str) -> str:
    """
    Get the name of the queue collection.

    Args:
        queue_name: Name of the queue collection

    Returns:
        str: The name of the queue collection
    """
    return f"queues.{queue_name}"

def get_kb_queue_name(kb_id: str) -> str:
    """
    Get the queue name for a specific KB.
    Each KB has its own queue to ensure sequential processing per KB.
    
    Args:
        kb_id: Knowledge base ID
        
    Returns:
        str: Queue name for the KB (e.g., "kb_index_507f1f77bcf86cd799439011")
    """
    return f"kb_index_{kb_id}"

async def send_msg(
    analytiq_client,
    queue_name: str,
    msg: Optional[Dict[str, Any]] = None
) -> str:
    """
    Send a message to the queue.

    Args:
        analytiq_client: The AnalytiqClient instance
        queue_name: Name of the queue collection
        msg_type: Type of message to send
        msg: Optional message data

    Returns:
        str: The ID of the created message
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    queue_collection_name = get_queue_collection_name(queue_name)
    queue_collection = db[queue_collection_name]

    msg_data = {
        "status": "pending",
        "created_at": datetime.now(UTC),
        "msg": msg
    }

    result = await queue_collection.insert_one(msg_data)
    msg_id = str(result.inserted_id)
    logger.info(f"Sent message: {msg_id} to {queue_name}")
    return msg_id

async def recv_msg(analytiq_client, queue_name: str) -> Optional[Dict[str, Any]]:
    """
    Receive and claim the next available message from the queue.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        queue_name: Name of the queue collection
    
    Returns:
        Optional[Dict]: The message document if found, None otherwise
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    queue_collection_name = get_queue_collection_name(queue_name)
    queue_collection = db[queue_collection_name]

    msg_data = await queue_collection.find_one_and_update(
        {"status": "pending"},
        {"$set": {"status": "processing"}},
        sort=[("created_at", 1)]
    )
    
    return msg_data

async def delete_msg(analytiq_client, queue_name: str, msg_id: str, status: str = "completed"):
    """
    Delete/complete a message by updating its status.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        queue_name: Name of the queue collection
        msg_id: The ID of the message to delete
        status: The final status to set (default: "completed")
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    queue_collection_name = get_queue_collection_name(queue_name)
    queue_collection = db[queue_collection_name]

    await queue_collection.update_one(
        {"_id": ObjectId(msg_id)},
        {"$set": {"status": status}}
    )
    logger.info(f"Deleted message {msg_id} from {queue_name} with status: {status}") 