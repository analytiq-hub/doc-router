"""
Schema tools for the agent: create, get, list, update, delete, validate.
Uses get_async_db(analytiq_client) for all DB access.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, UTC
from typing import Any

from bson import ObjectId
from jsonschema import Draft7Validator

import analytiq_data as ad

logger = logging.getLogger(__name__)


def _db(context: dict):
    return ad.common.get_async_db(context["analytiq_client"])


async def _get_schema_id_and_version(db, schema_id: str | None) -> tuple[str, int]:
    """Next version for existing schema_id or new schema_id. Uses given db.
    Caller must set name and organization_id on the schemas doc immediately after (for new schema_id)."""
    if schema_id is None:
        result = await db.schemas.insert_one({"schema_version": 1})
        return str(result.inserted_id), 1
    result = await db.schemas.find_one_and_update(
        {"_id": ObjectId(schema_id)},
        {"$inc": {"schema_version": 1}},
        upsert=True,
        return_document=True,
    )
    return schema_id, result["schema_version"]


def _validate_response_format(rf: dict) -> tuple[bool, str]:
    """Validate response_format dict (type json_schema, name, schema, Draft7). Returns (ok, error_msg)."""
    if not isinstance(rf, dict):
        return False, "response_format must be a dict"
    if rf.get("type") != "json_schema":
        return False, "response_format.type must be 'json_schema'"
    js = rf.get("json_schema")
    if not isinstance(js, dict):
        return False, "response_format.json_schema must be a dict"
    if "name" not in js or "schema" not in js:
        return False, "json_schema must contain 'name' and 'schema'"
    try:
        Draft7Validator.check_schema(js["schema"])
    except Exception as e:
        return False, f"Invalid JSON schema: {e}"
    return True, ""


async def create_schema(context: dict, params: dict) -> dict[str, Any]:
    """Creates a new schema in the org. Returns schema_revid or error."""
    org_id = context.get("organization_id")
    created_by = context.get("created_by", "agent")
    if not org_id:
        return {"error": "No organization context"}
    name = params.get("name")
    response_format = params.get("response_format")
    if not name:
        return {"error": "name is required"}
    if not response_format:
        return {"error": "response_format is required"}
    ok, err = _validate_response_format(response_format)
    if not ok:
        return {"error": err}
    db = _db(context)
    escaped = re.escape(name)
    existing = await db.schemas.find_one(
        {"name": {"$regex": f"^{escaped}$", "$options": "i"}, "organization_id": org_id}
    )
    schema_id, new_version = await _get_schema_id_and_version(
        db, str(existing["_id"]) if existing else None
    )
    await db.schemas.update_one(
        {"_id": ObjectId(schema_id)},
        {"$set": {"name": name, "organization_id": org_id}},
        upsert=True,
    )
    doc = {
        "schema_id": schema_id,
        "response_format": response_format,
        "schema_version": new_version,
        "created_at": datetime.now(UTC),
        "created_by": created_by,
    }
    result = await db.schema_revisions.insert_one(doc)
    revid = str(result.inserted_id)
    ws = context.get("working_state")
    if ws is not None:
        ws["schema_revid"] = revid
    return {"schema_revid": revid, "schema_id": schema_id, "name": name}


async def get_schema(context: dict, params: dict) -> dict[str, Any]:
    """Returns the full schema definition for schema_revid."""
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    schema_revid = params.get("schema_revid")
    if not schema_revid:
        return {"error": "schema_revid is required"}
    db = _db(context)
    revision = await db.schema_revisions.find_one({"_id": ObjectId(schema_revid)})
    if not revision:
        return {"error": "Schema not found"}
    schema = await db.schemas.find_one(
        {"_id": ObjectId(revision["schema_id"]), "organization_id": org_id}
    )
    if not schema:
        return {"error": "Schema not found or not in this organization"}
    revision["schema_revid"] = str(revision.pop("_id"))
    revision["name"] = schema["name"]
    return revision


async def list_schemas(context: dict, params: dict) -> dict[str, Any]:
    """Lists schemas in the org with optional skip, limit, name_search."""
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
    org_schemas = await db.schemas.find(query).to_list(None)
    if not org_schemas:
        return {"schemas": [], "total_count": 0, "skip": skip}
    schema_ids = [str(s["_id"]) for s in org_schemas]
    id_to_name = {str(s["_id"]): s["name"] for s in org_schemas}
    pipeline = [
        {"$match": {"schema_id": {"$in": schema_ids}}},
        {"$sort": {"_id": -1}},
        {"$group": {"_id": "$schema_id", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$sort": {"_id": -1}},
        {"$facet": {"total": [{"$count": "count"}], "schemas": [{"$skip": skip}, {"$limit": limit}]}},
    ]
    result = (await db.schema_revisions.aggregate(pipeline).to_list(length=1))[0]
    total = result["total"][0]["count"] if result["total"] else 0
    schemas = result["schemas"]
    for s in schemas:
        s["schema_revid"] = str(s.pop("_id"))
        s["name"] = id_to_name.get(s["schema_id"], "Unknown")
    return {"schemas": schemas, "total_count": total, "skip": skip}


async def update_schema(context: dict, params: dict) -> dict[str, Any]:
    """Creates a new version of an existing schema. Returns schema_revid."""
    org_id = context.get("organization_id")
    created_by = context.get("created_by", "agent")
    if not org_id:
        return {"error": "No organization context"}
    schema_id = params.get("schema_id")
    name = params.get("name")
    response_format = params.get("response_format")
    if not schema_id:
        return {"error": "schema_id is required"}
    if name is None and response_format is None:
        return {"error": "At least one of name or response_format is required"}
    db = _db(context)
    existing = await db.schemas.find_one(
        {"_id": ObjectId(schema_id), "organization_id": org_id}
    )
    if not existing:
        return {"error": "Schema not found"}
    latest = await db.schema_revisions.find_one(
        {"schema_id": schema_id}, sort=[("schema_version", -1)]
    )
    if not latest:
        return {"error": "Schema revision not found"}
    new_name = name if name is not None else existing["name"]
    new_rf = response_format if response_format is not None else latest["response_format"]
    if response_format is not None:
        ok, err = _validate_response_format(response_format)
        if not ok:
            return {"error": err}
    if new_name == existing["name"] and new_rf == latest.get("response_format"):
        return {
            "schema_revid": str(latest["_id"]),
            "schema_id": schema_id,
            "name": new_name,
            "message": "No changes",
        }
    _, new_version = await _get_schema_id_and_version(db, schema_id)
    if new_name != existing["name"]:
        await db.schemas.update_one(
            {"_id": ObjectId(schema_id)}, {"$set": {"name": new_name}}
        )
    new_doc = {
        "schema_id": schema_id,
        "response_format": new_rf,
        "schema_version": new_version,
        "created_at": datetime.now(UTC),
        "created_by": created_by,
    }
    result = await db.schema_revisions.insert_one(new_doc)
    revid = str(result.inserted_id)
    ws = context.get("working_state")
    if ws is not None:
        ws["schema_revid"] = revid
    return {"schema_revid": revid, "schema_id": schema_id, "name": new_name}


async def delete_schema(context: dict, params: dict) -> dict[str, Any]:
    """Deletes a schema. Fails if dependent prompts exist."""
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    schema_id = params.get("schema_id")
    if not schema_id:
        return {"error": "schema_id is required"}
    db = _db(context)
    schema = await db.schemas.find_one(
        {"_id": ObjectId(schema_id), "organization_id": org_id}
    )
    if not schema:
        return {"error": "Schema not found or not in this organization"}
    dependent = await db.prompt_revisions.find({"schema_id": schema_id}).to_list(None)
    if dependent:
        return {"error": f"Cannot delete schema: {len(dependent)} prompt(s) depend on it"}
    await db.schema_revisions.delete_many({"schema_id": schema_id})
    await db.schemas.delete_one({"_id": ObjectId(schema_id)})
    return {"message": "Schema deleted successfully"}


async def validate_schema(context: dict, params: dict) -> dict[str, Any]:
    """Validates a schema (JSON string or dict) for correctness and DocRouter compliance."""
    schema_arg = params.get("schema")
    if schema_arg is None:
        return {"error": "schema is required"}
    if isinstance(schema_arg, str):
        try:
            schema_arg = json.loads(schema_arg)
        except json.JSONDecodeError as e:
            return {"valid": False, "error": str(e)}
    if not isinstance(schema_arg, dict):
        return {"valid": False, "error": "schema must be a JSON object"}
    rf = schema_arg if schema_arg.get("type") == "json_schema" else None
    if not rf:
        return {"valid": False, "error": "Schema must have type 'json_schema' and json_schema field"}
    ok, err = _validate_response_format(rf)
    if not ok:
        return {"valid": False, "error": err}
    return {"valid": True}


async def validate_against_schema(context: dict, params: dict) -> dict[str, Any]:
    """Validates data against a schema revision."""
    org_id = context.get("organization_id")
    if not org_id:
        return {"error": "No organization context"}
    schema_revid = params.get("schema_revid")
    data = params.get("data")
    if not schema_revid:
        return {"error": "schema_revid is required"}
    if data is None:
        return {"error": "data is required"}
    db = _db(context)
    schema_doc = await db.schema_revisions.find_one({"_id": ObjectId(schema_revid)})
    if not schema_doc:
        return {"error": "Schema not found"}
    try:
        json_schema = schema_doc["response_format"]["json_schema"]["schema"]
    except (KeyError, TypeError):
        return {"valid": False, "errors": [{"message": "Schema has no json_schema.schema"}]}
    validator = Draft7Validator(json_schema)
    errors = list(validator.iter_errors(data))
    if not errors:
        return {"valid": True}
    formatted = [
        {"path": ".".join(str(p) for p in e.path) if e.path else "", "message": e.message}
        for e in errors
    ]
    return {"valid": False, "errors": formatted}
