"""
Tag tools for the agent: create, get, list, update, delete.
Uses get_async_db(analytiq_client) for all DB access.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, UTC
from typing import Any

from bson import ObjectId

import analytiq_data as ad

logger = logging.getLogger(__name__)


def _db(context: dict):
    return ad.common.get_async_db(context["analytiq_client"])


async def create_tag(context: dict, params: dict) -> dict[str, Any]:
    """Creates a new tag. Returns tag_id or error."""
    org_id = context.get("organization_id")
    created_by = context.get("created_by", "agent")
    if not org_id:
        return {"error": "No organization context"}
    name = params.get("name")
    if not name:
        return {"error": "name is required"}
    color = params.get("color")
    description = params.get("description")
    db = _db(context)
    existing = await db.tags.find_one(
        {"name": name, "organization_id": org_id}
    )
    if existing:
        return {"error": f"Tag with name '{name}' already exists"}
    doc = {
        "name": name,
        "color": color,
        "description": description,
        "created_at": datetime.now(UTC),
        "created_by": created_by,
        "organization_id": org_id,
    }
    result = await db.tags.insert_one(doc)
    return {"tag_id": str(result.inserted_id), "name": name}


async def get_tag(context: dict, params: dict) -> dict[str, Any]:
    """Returns tag details for tag_id."""
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    tag_id = params.get("tag_id")
    if not tag_id:
        return {"error": "tag_id is required"}
    db = _db(context)
    tag = await db.tags.find_one(
        {"_id": ObjectId(tag_id), "organization_id": org_id}
    )
    if not tag:
        return {"error": "Tag not found"}
    return {
        "id": str(tag["_id"]),
        "name": tag["name"],
        "color": tag.get("color"),
        "description": tag.get("description"),
        "created_at": tag["created_at"],
        "created_by": tag["created_by"],
    }


async def list_tags(context: dict, params: dict) -> dict[str, Any]:
    """Lists tags in the org with optional skip, limit, name_search."""
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    skip = int(params.get("skip", 0))
    limit = int(params.get("limit", 10))
    limit = min(max(limit, 1), 100)
    name_search = params.get("name_search")
    db = _db(context)
    query = {"organization_id": org_id}
    if name_search:
        query["name"] = {"$regex": re.escape(name_search), "$options": "i"}
    total = await db.tags.count_documents(query)
    cursor = db.tags.find(query).sort("_id", -1).skip(skip).limit(limit)
    tags = await cursor.to_list(length=None)
    return {
        "tags": [
            {
                "id": str(t["_id"]),
                "name": t["name"],
                "color": t.get("color"),
                "description": t.get("description"),
                "created_at": t["created_at"],
                "created_by": t["created_by"],
            }
            for t in tags
        ],
        "total_count": total,
        "skip": skip,
    }


async def update_tag(context: dict, params: dict) -> dict[str, Any]:
    """Updates a tag's name, color, or description."""
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    tag_id = params.get("tag_id")
    if not tag_id:
        return {"error": "tag_id is required"}
    name = params.get("name")
    color = params.get("color")
    description = params.get("description")
    db = _db(context)
    tag = await db.tags.find_one(
        {"_id": ObjectId(tag_id), "organization_id": org_id}
    )
    if not tag:
        return {"error": "Tag not found"}
    update = {}
    if name is not None:
        update["name"] = name
    if color is not None:
        update["color"] = color
    if description is not None:
        update["description"] = description
    if not update:
        return {"tag_id": tag_id, "name": tag["name"], "message": "No changes"}
    updated = await db.tags.find_one_and_update(
        {"_id": ObjectId(tag_id)},
        {"$set": update},
        return_document=True,
    )
    return {"tag_id": tag_id, "name": updated["name"]}


async def delete_tag(context: dict, params: dict) -> dict[str, Any]:
    """Deletes a tag. Fails if used by documents or prompts."""
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    tag_id = params.get("tag_id")
    if not tag_id:
        return {"error": "tag_id is required"}
    db = _db(context)
    tag = await db.tags.find_one(
        {"_id": ObjectId(tag_id), "organization_id": org_id}
    )
    if not tag:
        return {"error": "Tag not found"}
    used_doc = await db.docs.find_one({"tag_ids": tag_id})
    if used_doc:
        return {"error": f"Cannot delete tag '{tag['name']}' because it is assigned to documents"}
    used_prompt = await db.prompt_revisions.find_one({"tag_ids": tag_id})
    if used_prompt:
        return {"error": f"Cannot delete tag '{tag['name']}' because it is assigned to prompts"}
    await db.tags.delete_one({"_id": ObjectId(tag_id)})
    return {"message": "Tag deleted successfully"}
