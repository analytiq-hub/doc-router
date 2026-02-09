"""
Prompt tools for the agent: create, get, list, update, delete.
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


async def _get_prompt_id_and_version(db, prompt_id: str | None) -> tuple[str, int]:
    """Next version for existing prompt_id or new prompt_id. Caller must set name and organization_id on prompts doc immediately after (for new prompt_id)."""
    if prompt_id is None:
        result = await db.prompts.insert_one({"prompt_version": 1})
        return str(result.inserted_id), 1
    result = await db.prompts.find_one_and_update(
        {"_id": ObjectId(prompt_id)},
        {"$inc": {"prompt_version": 1}},
        upsert=True,
        return_document=True,
    )
    return prompt_id, result["prompt_version"]


async def create_prompt(context: dict, params: dict) -> dict[str, Any]:
    """Creates a new prompt. Returns prompt_revid or error."""
    org_id = context.get("organization_id")
    created_by = context.get("created_by", "agent")
    if not org_id:
        return {"error": "No organization context"}
    name = params.get("name")
    content = params.get("content")
    if not name:
        return {"error": "name is required"}
    if content is None:
        return {"error": "content is required"}
    schema_id = params.get("schema_id")
    schema_version = params.get("schema_version")
    model = params.get("model", "gpt-4o-mini")
    tag_ids = params.get("tag_ids") or []
    kb_id = params.get("kb_id")
    db = _db(context)
    if schema_id:
        if schema_version is not None:
            schema = await db.schema_revisions.find_one(
                {"schema_id": schema_id, "schema_version": schema_version}
            )
        else:
            schema = await db.schema_revisions.find_one(
                {"schema_id": schema_id}, sort=[("schema_version", -1)]
            )
        if not schema:
            return {"error": f"Schema {schema_id} not found"}
        schema_version = schema["schema_version"]
    else:
        schema_version = None
    if tag_ids:
        existing = await db.tags.find(
            {"_id": {"$in": [ObjectId(t) for t in tag_ids]}, "organization_id": org_id}
        ).to_list(None)
        existing_ids = {str(t["_id"]) for t in existing}
        invalid = set(tag_ids) - existing_ids
        if invalid:
            return {"error": f"Invalid tag IDs: {list(invalid)}"}
    if kb_id:
        kb = await db.knowledge_bases.find_one(
            {"_id": ObjectId(kb_id), "organization_id": org_id}
        )
        if not kb or kb.get("status") != "active":
            return {"error": f"Knowledge base {kb_id} not found or not active"}
    existing_prompt = await db.prompts.find_one(
        {"name": name, "organization_id": org_id}
    )
    prompt_id, new_version = await _get_prompt_id_and_version(
        db, str(existing_prompt["_id"]) if existing_prompt else None
    )
    await db.prompts.update_one(
        {"_id": ObjectId(prompt_id)},
        {"$set": {"name": name, "organization_id": org_id}},
        upsert=True,
    )
    doc = {
        "prompt_id": prompt_id,
        "content": content,
        "prompt_version": new_version,
        "created_at": datetime.now(UTC),
        "created_by": created_by,
        "tag_ids": tag_ids,
        "model": model,
        "organization_id": org_id,
        "kb_id": kb_id,
    }
    if schema_id is not None:
        doc["schema_id"] = schema_id
        doc["schema_version"] = schema_version
    result = await db.prompt_revisions.insert_one(doc)
    revid = str(result.inserted_id)
    ws = context.get("working_state")
    if ws is not None:
        ws["prompt_revid"] = revid
    return {"prompt_revid": revid, "prompt_id": prompt_id, "name": name}


async def get_prompt(context: dict, params: dict) -> dict[str, Any]:
    """Returns the full prompt for prompt_revid."""
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    prompt_revid = params.get("prompt_revid")
    if not prompt_revid:
        return {"error": "prompt_revid is required"}
    db = _db(context)
    revision = await db.prompt_revisions.find_one({"_id": ObjectId(prompt_revid)})
    if not revision:
        return {"error": "Prompt not found"}
    prompt = await db.prompts.find_one(
        {"_id": ObjectId(revision["prompt_id"]), "organization_id": org_id}
    )
    if not prompt:
        return {"error": "Prompt not found or not in this organization"}
    revision["prompt_revid"] = str(revision.pop("_id"))
    revision["name"] = prompt["name"]
    return revision


async def list_prompts(context: dict, params: dict) -> dict[str, Any]:
    """Lists prompts in the org with optional filters."""
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    skip = int(params.get("skip", 0))
    limit = int(params.get("limit", 10))
    limit = min(max(limit, 1), 100)
    name_search = params.get("name_search")
    document_id = params.get("document_id")
    tag_ids = params.get("tag_ids")
    if isinstance(tag_ids, str):
        tag_ids = [t.strip() for t in tag_ids.split(",")] if tag_ids else []
    db = _db(context)
    query = {"organization_id": org_id}
    if name_search:
        query["name"] = {"$regex": re.escape(name_search), "$options": "i"}
    org_prompts = await db.prompts.find(query).to_list(None)
    if not org_prompts:
        return {"prompts": [], "total_count": 0, "skip": skip}
    prompt_ids = [str(p["_id"]) for p in org_prompts]
    id_to_name = {str(p["_id"]): p["name"] for p in org_prompts}
    pipeline = [
        {"$match": {"prompt_id": {"$in": prompt_ids}}},
        {"$sort": {"_id": -1}},
        {"$group": {"_id": "$prompt_id", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$sort": {"_id": -1}},
    ]
    if document_id:
        doc = await db.docs.find_one(
            {"_id": ObjectId(document_id), "organization_id": org_id}
        )
        if doc and doc.get("tag_ids"):
            pipeline.append({"$match": {"tag_ids": {"$in": doc["tag_ids"]}}})
    if tag_ids:
        pipeline.append({"$match": {"tag_ids": {"$all": tag_ids}}})
    pipeline.append({
        "$facet": {
            "total": [{"$count": "count"}],
            "prompts": [{"$skip": skip}, {"$limit": limit}],
        }
    })
    result = (await db.prompt_revisions.aggregate(pipeline).to_list(length=1))[0]
    total = result["total"][0]["count"] if result["total"] else 0
    prompts = result["prompts"]
    for p in prompts:
        p["prompt_revid"] = str(p.pop("_id"))
        p["name"] = id_to_name.get(p["prompt_id"], "Unknown")
    return {"prompts": prompts, "total_count": total, "skip": skip}


async def update_prompt(context: dict, params: dict) -> dict[str, Any]:
    """Creates a new version of an existing prompt."""
    org_id = context.get("organization_id")
    created_by = context.get("created_by", "agent")
    if not org_id:
        return {"error": "No organization context"}
    prompt_id = params.get("prompt_id")
    if not prompt_id:
        return {"error": "prompt_id is required"}
    content = params.get("content")
    schema_id = params.get("schema_id")
    tag_ids = params.get("tag_ids")
    model = params.get("model")
    db = _db(context)
    existing = await db.prompts.find_one(
        {"_id": ObjectId(prompt_id), "organization_id": org_id}
    )
    if not existing:
        return {"error": "Prompt not found"}
    latest = await db.prompt_revisions.find_one(
        {"prompt_id": prompt_id}, sort=[("prompt_version", -1)]
    )
    if not latest:
        return {"error": "Prompt revision not found"}
    new_content = content if content is not None else latest["content"]
    new_schema_id = schema_id if schema_id is not None else latest.get("schema_id")
    new_schema_version = latest.get("schema_version")
    if new_schema_id and schema_id is not None:
        schema = await db.schema_revisions.find_one(
            {"schema_id": new_schema_id}, sort=[("schema_version", -1)]
        )
        if schema:
            new_schema_version = schema["schema_version"]
    new_tag_ids = tag_ids if tag_ids is not None else latest.get("tag_ids") or []
    new_model = model if model is not None else latest.get("model", "gpt-4o-mini")
    if new_tag_ids:
        existing_tags = await db.tags.find(
            {"_id": {"$in": [ObjectId(t) for t in new_tag_ids]}, "organization_id": org_id}
        ).to_list(None)
        existing_ids = {str(t["_id"]) for t in existing_tags}
        if set(new_tag_ids) - existing_ids:
            return {"error": "Invalid tag IDs"}
    _, new_version = await _get_prompt_id_and_version(db, prompt_id)
    doc = {
        "prompt_id": prompt_id,
        "content": new_content,
        "schema_id": new_schema_id,
        "schema_version": new_schema_version,
        "prompt_version": new_version,
        "created_at": datetime.now(UTC),
        "created_by": created_by,
        "tag_ids": new_tag_ids,
        "model": new_model,
        "organization_id": org_id,
        "kb_id": latest.get("kb_id"),
    }
    result = await db.prompt_revisions.insert_one(doc)
    revid = str(result.inserted_id)
    ws = context.get("working_state")
    if ws is not None:
        ws["prompt_revid"] = revid
    return {"prompt_revid": revid, "prompt_id": prompt_id, "name": existing["name"]}


async def delete_prompt(context: dict, params: dict) -> dict[str, Any]:
    """Deletes a prompt."""
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    prompt_id = params.get("prompt_id")
    if not prompt_id:
        return {"error": "prompt_id is required"}
    db = _db(context)
    prompt = await db.prompts.find_one(
        {"_id": ObjectId(prompt_id), "organization_id": org_id}
    )
    if not prompt:
        return {"error": "Prompt not found or not in this organization"}
    await db.prompt_revisions.delete_many({"prompt_id": prompt_id})
    await db.prompts.delete_one({"_id": ObjectId(prompt_id)})
    return {"message": "Prompt deleted successfully"}
