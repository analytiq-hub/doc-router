from datetime import datetime, UTC, timedelta
from typing import Optional, Dict, Any
from bson import ObjectId
import logging
import os

from pymongo import ReturnDocument

import analytiq_data as ad

logger = logging.getLogger(__name__)


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


QUEUE_VISIBILITY_TIMEOUT_SECS = _get_int_env("QUEUE_VISIBILITY_TIMEOUT_SECS", 900)  # 15 min
MAX_QUEUE_ATTEMPTS = _get_int_env("MAX_QUEUE_ATTEMPTS", 3)


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
        "attempts": 0,
        "msg": msg,
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

    now = datetime.now(UTC)
    lease_cutoff = now - timedelta(seconds=QUEUE_VISIBILITY_TIMEOUT_SECS)

    query = {
        "$or": [
            {"status": "pending", "attempts": {"$lt": MAX_QUEUE_ATTEMPTS}},
            {
                "status": "processing",
                "processing_started_at": {"$lte": lease_cutoff},
                "attempts": {"$lt": MAX_QUEUE_ATTEMPTS},
            },
        ]
    }

    update = {
        "$set": {
            "status": "processing",
            "processing_started_at": now,
        },
        "$inc": {"attempts": 1},
    }

    msg_data = await queue_collection.find_one_and_update(
        query,
        update,
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )

    if msg_data:
        logger.info(
            f"Claimed message {msg_data.get('_id')} from {queue_name} "
            f"(attempt {msg_data.get('attempts')}, status={msg_data.get('status')})"
        )

    return msg_data

async def delete_msg(analytiq_client, queue_name: str, msg_id: str):
    """
    Delete a completed message from the queue.

    Args:
        analytiq_client: The AnalytiqClient instance
        queue_name: Name of the queue collection
        msg_id: The ID of the message to delete
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    queue_collection_name = get_queue_collection_name(queue_name)
    queue_collection = db[queue_collection_name]

    await queue_collection.delete_one({"_id": ObjectId(msg_id)})
    logger.info(f"Deleted message {msg_id} from {queue_name}") 


async def report_last_error(
    analytiq_client,
    queue_name: str,
    msg_id: str,
    error: str,
) -> None:
    """
    Unified non-terminal error reporting: sets last_error / failed_at on the queue doc.

    Pass the same string you would surface in logs (e.g. ``str(exc)``).
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    collection = db[get_queue_collection_name(queue_name)]
    try:
        await collection.update_one(
            {"_id": ObjectId(msg_id)},
            {
                "$set": {
                    "last_error": error,
                    "last_error_at": datetime.now(UTC),
                }
            },
        )
    except Exception as e:
        logger.warning(
            "report_last_error failed queue=%s msg_id=%s: %s",
            queue_name,
            msg_id,
            e,
        )


async def recover_stale_messages(analytiq_client, queue_name: str) -> int:
    """
    Recover stale processing messages for a queue by resetting them to pending.

    This function is idempotent and safe to call repeatedly. It only touches
    messages that:
    - Are in "processing" status (not dead_letter)
    - Have processing_started_at older than the visibility timeout

    For each recovered message, ``attempts`` is decremented by 1 (floored at 0)
    so a claim that never finished (e.g. process killed) does not permanently
    consume a retry. Stuck rows with attempts == MAX_QUEUE_ATTEMPTS are included.
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    queue_collection_name = get_queue_collection_name(queue_name)
    queue_collection = db[queue_collection_name]

    now = datetime.now(UTC)
    lease_cutoff = now - timedelta(seconds=QUEUE_VISIBILITY_TIMEOUT_SECS)

    # Aggregation pipeline update: pending + refund one claim + drop lease timestamp
    result = await queue_collection.update_many(
        {
            "status": "processing",
            "processing_started_at": {"$lte": lease_cutoff},
        },
        [
            {
                "$set": {
                    "status": "pending",
                    "attempts": {
                        "$max": [
                            0,
                            {
                                "$subtract": [
                                    {"$ifNull": ["$attempts", 0]},
                                    1,
                                ]
                            },
                        ]
                    },
                }
            },
            {"$unset": "processing_started_at"},
        ],
    )

    recovered = getattr(result, "modified_count", 0)
    if recovered:
        logger.info(
            f"Recovered {recovered} stale messages in {queue_name} "
            f"(visibility_timeout={QUEUE_VISIBILITY_TIMEOUT_SECS}s, attempts decremented)"
        )
    return recovered


_RELEASE_IN_FLIGHT_PIPELINE = [
    {
        "$set": {
            "status": "pending",
            "attempts": {
                "$max": [
                    0,
                    {
                        "$subtract": [
                            {"$ifNull": ["$attempts", 0]},
                            1,
                        ]
                    },
                ]
            },
        }
    },
    {"$unset": "processing_started_at"},
]


async def release_all_in_flight_queue_claims(db) -> int:
    """
    Reset every ``processing`` job queue document to ``pending``, decrement ``attempts``
    by 1 (floored at 0), and clear ``processing_started_at``.

    Invoked from ``run_migrations`` on every deploy (not a versioned migration itself),
    so jobs stuck in ``processing`` due to a worker killed mid-job during a restart are
    recovered automatically.
    """
    queue_collections = ["queues.ocr", "queues.llm", "queues.webhook", "queues.kb_index"]
    all_collections = await db.list_collection_names()
    for coll_name in all_collections:
        if coll_name.startswith("queues.kb_index_") and coll_name not in queue_collections:
            queue_collections.append(coll_name)

    total_modified = 0
    for coll_name in queue_collections:
        if coll_name not in all_collections:
            continue
        result = await db[coll_name].update_many(
            {"status": "processing"},
            _RELEASE_IN_FLIGHT_PIPELINE,
        )
        n = getattr(result, "modified_count", 0)
        if n:
            logger.info(f"release_all_in_flight_queue_claims: {coll_name} modified={n}")
            total_modified += n
    if total_modified:
        logger.info(f"release_all_in_flight_queue_claims: total_modified={total_modified}")
    return total_modified


async def move_to_dlq(analytiq_client, queue_name: str, msg_id: str, error: str) -> None:
    """
    Move a failed message to dead letter state after max attempts.

    Dead letter messages should be inspected before reprocessing.
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    collection = db[get_queue_collection_name(queue_name)]

    await collection.update_one(
        {"_id": ObjectId(msg_id)},
        {
            "$set": {
                "status": "dead_letter",
                "failed_at": datetime.now(UTC),
                "last_error": error,
            }
        },
    )
    logger.warning(f"Message {msg_id} moved to dead letter in {queue_name}: {error}")