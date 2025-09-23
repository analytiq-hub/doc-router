from datetime import datetime, UTC
import asyncio
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

async def recv_msg_w_tmo(
    analytiq_client,
    queue_name: str,
    timeout_secs: float,
) -> Optional[Dict[str, Any]]:
    """
    Wait up to timeout_secs for a message to become available and atomically claim it.

    Strategy:
    1) Try to claim immediately using the same atomic find_one_and_update as recv_msg.
    2) If nothing is available, attempt to use MongoDB change streams to wait for an
       insert/update that results in a pending message, then try to claim again.
    3) If change streams are unavailable (e.g., standalone MongoDB), fall back to
       periodic polling until timeout.

    Args:
        analytiq_client: The AnalytiqClient instance
        queue_name: Name of the queue collection
        timeout_secs: Maximum time to wait in seconds

    Returns:
        Optional[Dict[str, Any]]: The claimed message document if found, None otherwise
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    queue_collection_name = get_queue_collection_name(queue_name)
    queue_collection = db[queue_collection_name]

    # Fast path: try to claim immediately
    msg_data = await queue_collection.find_one_and_update(
        {"status": "pending"},
        {"$set": {"status": "processing"}},
        sort=[("created_at", 1)],
    )
    if msg_data:
        return msg_data

    deadline = asyncio.get_event_loop().time() + max(0.0, float(timeout_secs))

    # Try change streams first; if not supported, fall back to polling
    try:
        pipeline = [
            {"$match": {"operationType": {"$in": ["insert", "update", "replace"]}}},
            {"$match": {"fullDocument.status": "pending"}},
        ]

        # full_document='updateLookup' ensures fullDocument is present for updates
        async with queue_collection.watch(
            pipeline=pipeline,
            full_document='updateLookup',
        ) as change_stream:
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return None
                try:
                    # Wait for the next change or timeout
                    change = await asyncio.wait_for(change_stream.next(), timeout=remaining)
                except asyncio.TimeoutError:
                    return None

                # A potential pending message appeared; try to claim again
                msg_data = await queue_collection.find_one_and_update(
                    {"status": "pending"},
                    {"$set": {"status": "processing"}},
                    sort=[("created_at", 1)],
                )
                if msg_data:
                    return msg_data
                # Otherwise continue waiting until timeout
    except Exception:
        logger.warning(f"Change streams unavailable or error; falling back to polling")
        # Change streams unavailable or error; fall back to polling
        poll_interval = 0.5
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                return None
            # Try to claim
            msg_data = await queue_collection.find_one_and_update(
                {"status": "pending"},
                {"$set": {"status": "processing"}},
                sort=[("created_at", 1)],
            )
            if msg_data:
                return msg_data
            await asyncio.sleep(min(poll_interval, max(0.0, remaining)))

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