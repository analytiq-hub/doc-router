"""
Persistence for document agent chat threads.
Stored in MongoDB collection agent_threads; scoped by organization_id, document_id, and created_by (user).
"""
from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Any

from bson import ObjectId

import analytiq_data as ad

logger = logging.getLogger(__name__)

COLLECTION = "agent_threads"


def _thread_doc(
    organization_id: str,
    document_id: str,
    created_by: str,
    *,
    title: str | None = None,
    messages: list[dict] | None = None,
    extraction: dict | None = None,
    model: str | None = None,
) -> dict:
    now = datetime.now(UTC)
    doc: dict = {
        "organization_id": organization_id,
        "document_id": document_id,
        "created_by": created_by,
        "title": title or "New chat",
        "messages": messages or [],
        "extraction": extraction or {},
        "created_at": now,
        "updated_at": now,
    }
    if model is not None:
        doc["model"] = model
    return doc


async def list_threads(
    analytiq_client: Any,
    organization_id: str,
    document_id: str,
    user_id: str,
    limit: int = 50,
) -> list[dict]:
    """
    List threads for a document owned by the user (metadata only: id, title, created_at, updated_at).
    Most recent first.
    """
    db = ad.common.get_async_db(analytiq_client)
    coll = db[COLLECTION]
    cursor = coll.find(
        {"organization_id": organization_id, "document_id": document_id, "created_by": user_id},
        projection={"title": 1, "created_at": 1, "updated_at": 1},
    ).sort("updated_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [
        {
            "id": str(d["_id"]),
            "title": d.get("title", "New chat"),
            "created_at": d.get("created_at"),
            "updated_at": d.get("updated_at"),
        }
        for d in docs
    ]


async def get_thread(
    analytiq_client: Any,
    thread_id: str,
    organization_id: str,
    user_id: str,
) -> dict | None:
    """Get a single thread by id (full doc including messages and extraction). User must own the thread."""
    db = ad.common.get_async_db(analytiq_client)
    coll = db[COLLECTION]
    doc = await coll.find_one(
        {"_id": ObjectId(thread_id), "organization_id": organization_id, "created_by": user_id}
    )
    if not doc:
        return None
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title", "New chat"),
        "messages": doc.get("messages", []),
        "extraction": doc.get("extraction") or {},
        "model": doc.get("model"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


async def create_thread(
    analytiq_client: Any,
    organization_id: str,
    document_id: str,
    created_by: str,
    title: str | None = None,
) -> str:
    """Create a new thread; returns thread id."""
    db = ad.common.get_async_db(analytiq_client)
    coll = db[COLLECTION]
    doc = _thread_doc(organization_id, document_id, created_by, title=title)
    result = await coll.insert_one(doc)
    return str(result.inserted_id)


async def append_messages(
    analytiq_client: Any,
    thread_id: str,
    organization_id: str,
    user_id: str,
    new_messages: list[dict],
    extraction: dict | None = None,
    model: str | None = None,
) -> bool:
    """
    Append messages to a thread and optionally set extraction and model.
    new_messages: list of { role, content?, tool_calls? } in API format.
    User must own the thread.
    """
    if not new_messages:
        return True
    db = ad.common.get_async_db(analytiq_client)
    coll = db[COLLECTION]
    now = datetime.now(UTC)
    update: dict = {
        "$set": {"updated_at": now},
        "$push": {"messages": {"$each": new_messages}},
    }
    if extraction is not None:
        update["$set"]["extraction"] = extraction
    if model is not None:
        update["$set"]["model"] = model
    result = await coll.update_one(
        {"_id": ObjectId(thread_id), "organization_id": organization_id, "created_by": user_id},
        update,
    )
    return result.modified_count > 0


async def truncate_and_append_messages(
    analytiq_client: Any,
    thread_id: str,
    organization_id: str,
    user_id: str,
    keep_message_count: int,
    new_messages: list[dict],
    extraction: dict | None = None,
    model: str | None = None,
) -> bool:
    """
    Keep only the first keep_message_count messages in the thread, then append new_messages.
    Used when the user resubmits from a prior turn so the persisted thread forgets later turns.
    User must own the thread.
    """
    if keep_message_count < 0:
        keep_message_count = 0
    db = ad.common.get_async_db(analytiq_client)
    coll = db[COLLECTION]
    doc = await coll.find_one(
        {"_id": ObjectId(thread_id), "organization_id": organization_id, "created_by": user_id},
        projection={"messages": 1},
    )
    if not doc:
        return False
    messages = doc.get("messages", [])
    kept = messages[:keep_message_count] if messages else []
    final_messages = kept + list(new_messages)
    now = datetime.now(UTC)
    update: dict = {"$set": {"messages": final_messages, "updated_at": now}}
    if extraction is not None:
        update["$set"]["extraction"] = extraction
    if model is not None:
        update["$set"]["model"] = model
    result = await coll.update_one(
        {"_id": ObjectId(thread_id), "organization_id": organization_id, "created_by": user_id},
        update,
    )
    return result.modified_count > 0


async def update_thread_title(
    analytiq_client: Any,
    thread_id: str,
    organization_id: str,
    user_id: str,
    title: str,
) -> bool:
    """Update thread title (e.g. first user message snippet). User must own the thread."""
    db = ad.common.get_async_db(analytiq_client)
    coll = db[COLLECTION]
    result = await coll.update_one(
        {"_id": ObjectId(thread_id), "organization_id": organization_id, "created_by": user_id},
        {"$set": {"title": title, "updated_at": datetime.now(UTC)}},
    )
    return result.modified_count > 0


async def delete_thread(
    analytiq_client: Any,
    thread_id: str,
    organization_id: str,
    user_id: str,
) -> bool:
    """Delete a thread. Returns True if a document was deleted. User must own the thread."""
    db = ad.common.get_async_db(analytiq_client)
    coll = db[COLLECTION]
    result = await coll.delete_one(
        {"_id": ObjectId(thread_id), "organization_id": organization_id, "created_by": user_id}
    )
    return result.deleted_count > 0
