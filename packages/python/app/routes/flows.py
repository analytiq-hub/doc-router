from __future__ import annotations

"""Flow CRUD + execution routes (v1 scaffolding) as defined in `docs/flows.md`."""

import json
import logging
import asyncio
from datetime import datetime, UTC
from typing import Any, Optional, List, Literal

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request, UploadFile, File, Form
from starlette.responses import Response
from uuid import uuid4
from datetime import timedelta
from pydantic import BaseModel, Field, ConfigDict

import analytiq_data as ad
from analytiq_data.docrouter_flows.document_flow_sidebar import (
    get_document_flow_result,
    list_matching_flows_for_document,
    rerun_flow_for_document,
)
from analytiq_data.docrouter_flows.bulk_analyze import bulk_analyze_flow_executions

from app.auth import get_org_user
from app.models import User



logger = logging.getLogger(__name__)
flows_router = APIRouter(tags=["flows"])

# Pinned binary uploads: refuse bodies over this size; only ``MAX + 1`` bytes are read from the stream.
MAX_PIN_UPLOAD_BYTES = 50 * 1024 * 1024

# Preview: cap serialized JSON per run_data node entry to limit memory/CPU from pathological payloads.
_MAX_PREVIEW_RUN_DATA_ENTRY_BYTES = 512_000

_REDACT_TRIGGER_HEADER_KEYS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
        "x-amz-security-token",
        "x-amzn-authorization",
    }
)


def _sanitize_inbound_webhook_headers(request: Request) -> dict[str, str]:
    """Avoid persisting secrets from inbound webhook HTTP headers into execution documents."""

    out: dict[str, str] = {}
    for k, v in request.headers.items():
        lk = k.lower()
        if lk in _REDACT_TRIGGER_HEADER_KEYS or lk.startswith("x-amz-") or lk.startswith("x-forwarded-authorization"):
            out[k] = "[redacted]"
        else:
            out[k] = v
    return out


def _inbound_webhook_canonical_public_url(request: Request) -> str:
    """
    Client-facing webhook URL as seen beyond reverse proxies.

    Prefer ``X-Forwarded-Proto`` / ``X-Forwarded-Host`` when present so stored URLs match
    what Postman/callers hit (``https`` + public host).
    """

    xf_proto = request.headers.get("x-forwarded-proto")
    proto = ""
    if isinstance(xf_proto, str) and xf_proto.strip():
        proto = xf_proto.strip().split(",")[0].strip().lower()
    if not proto:
        proto = (request.url.scheme or "https").lower()

    xf_host = request.headers.get("x-forwarded-host")
    host = ""
    if isinstance(xf_host, str) and xf_host.strip():
        host = xf_host.strip().split(",")[0].strip()
    if not host:
        hh = request.headers.get("host")
        if isinstance(hh, str) and hh.strip():
            host = hh.strip()
    if not host:
        host = request.url.netloc or "localhost"

    path = request.url.path or ""
    query = request.url.query
    if query:
        return f"{proto}://{host}{path}?{query}"
    return f"{proto}://{host}{path}"


def _safe_webhook_blob_segment(part: str) -> str:
    """Single path segment for GridFS keys (no slashes, no `..` segments after rewrite)."""

    p = "".join(c if (c.isalnum() or c in "._-") else "_" for c in part)
    return (p[:120] if p else "file")


def _flow_pins_keys_from_pin_data(pin_data: Any, *, prefix: str) -> set[str]:
    """
    Collect `flow_pins` GridFS keys referenced by a pin_data payload, filtered by ``key.startswith(prefix)``.

    For save-step cleanup use ``prefix="pin/"`` so keys keep working when the baked-in upload revision id
    (``pin/{upload_revid}/…``) no longer equals the superseded revision id.

    Traverses every list under ``main`` (all output lanes), not only lane 0, so GC matches
    references stored in secondary lanes. (Runtime pin application for executions still reads
    lane 0 only — see ``coerce_pin_data_node_output``.)

    pin_data is expected to be `{ node_id: { main: [[ ... ], [ ... ]] } }` but this function is
    intentionally permissive and will ignore unknown shapes.
    """

    out: set[str] = set()
    if not pin_data or not isinstance(pin_data, dict):
        return out
    for node_entry in pin_data.values():
        if not isinstance(node_entry, dict):
            continue
        main = node_entry.get("main")
        if not isinstance(main, list) or not main:
            continue
        for lane in main:
            if not isinstance(lane, list):
                continue
            for it in lane:
                if not isinstance(it, dict):
                    continue
                binary = it.get("binary")
                if not isinstance(binary, dict):
                    continue
                for ref in binary.values():
                    if not isinstance(ref, dict):
                        continue
                    sid = ref.get("storage_id")
                    if not isinstance(sid, str) or not sid.strip():
                        continue
                    parts = sid.strip().split(":", 1)
                    if len(parts) != 2 or parts[0] != "flow_pins":
                        continue
                    key = parts[1]
                    if key.startswith(prefix):
                        out.add(key)
    return out


def _flow_pins_key_in_pin_data(pin_data: Any, key: str) -> bool:
    """True when ``key`` is a ``flow_pins`` ref embedded in ``pin_data`` (any upload-time rev segment)."""

    if not key.startswith("pin/"):
        return False
    return key in _flow_pins_keys_from_pin_data(pin_data, prefix="pin/")


def _flow_pins_key_authorized_for_revision(pin_data: Any, key: str, flow_revid: str) -> bool:
    """
    Allow download when the key is referenced in ``pin_data`` (upload rev may differ from ``flow_revid``),
    or when the key is scoped to this revision id (upload not yet saved into ``pin_data``).
    """

    if not key.startswith("pin/"):
        return False
    if _flow_pins_key_in_pin_data(pin_data, key):
        return True
    return key.startswith(f"pin/{flow_revid}/")


async def _require_flow_pins_key_for_revision(
    db: Any,
    *,
    flow_id: str,
    flow_revid: str,
    key: str,
) -> None:
    """Raise 403/404 when ``key`` is not allowed for this revision."""

    if not key.startswith("pin/"):
        raise HTTPException(status_code=400, detail="Invalid storage_id")
    try:
        rev_oid = ObjectId(flow_revid)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Revision not found") from None
    rev = await db.flow_revisions.find_one({"_id": rev_oid, "flow_id": flow_id})
    if not rev:
        raise HTTPException(status_code=404, detail="Revision not found")
    if not _flow_pins_key_authorized_for_revision(rev.get("pin_data"), key, flow_revid):
        raise HTTPException(status_code=403, detail="Blob key is not referenced by this revision")


def _safe_content_disposition_filename(fname: str) -> str:
    """
    Safe ``filename="…"`` value for RFC 7230 field lines: ASCII printable only.

    Excludes backslash and double-quote (header metacharacters) and control characters (U+0000–U+001F)
    via ``str.isprintable()``, preventing header injection (e.g. folded lines / extra headers).
    """

    s = "".join(
        ch if ch.isascii() and ch.isprintable() and ch not in {'\\', '"'} else "_" for ch in fname.strip()
    )[:240]
    return s or "file"


def _mime_essence(mime_raw: str) -> str:
    """Normalize to lowercase ``type/subtype`` before ``;parameters`` (CR/LF stripped)."""

    if not isinstance(mime_raw, str):
        return "application/octet-stream"
    pre = mime_raw.strip()
    base = pre.split(";", maxsplit=1)[0].strip().lower().replace("\r", "").replace("\n", "")
    return base or "application/octet-stream"


def _pin_blob_mime_allows_inline(mime_raw: str) -> bool:
    """
    Only ``image/*`` (excluding SVG/XML vector HTML) or ``application/pdf`` may preview inline.

    User-supplied ``mime_type`` is stored with blobs; echoed on download—never treat ``text/html`` etc.
    as inline (stored XSS via ``Content-Disposition: inline`` + browser rendering).
    """

    essence = _mime_essence(mime_raw)
    if not essence:
        return False
    if essence.startswith("image/"):
        return not essence.startswith("image/svg+xml")
    return essence == "application/pdf"


def _blob_response_media_type(stored_mime: str, *, content_disposition_is_inline: bool) -> str:
    """
    Echo a conservative ``Content-Type`` for arbitrary stored metadata.

    - Inline: only safe preview essences keep their type (images except SVG, PDF); else octet-stream.
    - Attachment: never echo ``text/*`` as such; downgrade ``application/*`` except PDF to octet-stream
      so uploads cannot force ``application/javascript``, ``application/xhtml+xml``, etc.
    """

    essence = _mime_essence(stored_mime)
    if content_disposition_is_inline and _pin_blob_mime_allows_inline(stored_mime):
        return essence
    if content_disposition_is_inline:
        return "application/octet-stream"
    if essence.startswith("text/"):
        return "application/octet-stream"
    if essence.startswith("application/"):
        return essence if essence == "application/pdf" else "application/octet-stream"
    return essence


def _parse_binary_storage_id(storage_id: str) -> tuple[str, str]:
    """Parse ``BinaryRef.storage_id`` as ``bucket:key``."""

    sid = storage_id.strip()
    parts = sid.split(":", 1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise HTTPException(status_code=400, detail="Invalid storage_id")
    return parts[0].strip(), parts[1].strip()


def _gridfs_blob_bytes(result: dict[str, Any] | None) -> bytes:
    if not result:
        raise HTTPException(status_code=404, detail="Blob not found")
    blob_raw = result.get("blob")
    if blob_raw is None:
        raise HTTPException(status_code=404, detail="Blob payload missing")
    return blob_raw if isinstance(blob_raw, (bytes, bytearray)) else bytes(blob_raw)


def _gridfs_meta_mime_and_filename(meta_raw: Any) -> tuple[str, str]:
    meta: dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
    mime = meta.get("mime_type") if isinstance(meta.get("mime_type"), str) else "application/octet-stream"
    fname = meta.get("file_name") if isinstance(meta.get("file_name"), str) else ""
    return mime, fname


def _binary_blob_http_response(
    *,
    blob: bytes,
    mime: str,
    file_name: str,
    action: Literal["view", "download"],
) -> Response:
    headers: dict[str, str] = {}
    want_inline = action == "view" and _pin_blob_mime_allows_inline(mime)
    disp = "inline" if want_inline else "attachment"
    if file_name.strip():
        safe = _safe_content_disposition_filename(file_name)
        headers["Content-Disposition"] = f'{disp}; filename="{safe}"'
    elif not want_inline:
        headers["Content-Disposition"] = disp
    media_type = _blob_response_media_type(mime, content_disposition_is_inline=want_inline)
    return Response(content=blob, media_type=media_type, headers=headers)


async def _load_org_document_file_blob(
    db,
    analytiq_client,
    *,
    organization_id: str,
    file_key: str,
) -> tuple[bytes, str, str]:
    """Load a permanent document GridFS object after verifying org ownership."""

    doc_rec = await db.docs.find_one(
        {
            "organization_id": organization_id,
            "$or": [{"pdf_file_name": file_key}, {"mongo_file_name": file_key}],
        }
    )
    if not doc_rec:
        raise HTTPException(status_code=404, detail="Blob not found")

    file_result = await ad.common.get_file_async(analytiq_client, file_key)
    if not file_result:
        raise HTTPException(status_code=404, detail="Blob not found")

    blob_bytes = _gridfs_blob_bytes(file_result)
    meta = file_result.get("metadata") if isinstance(file_result.get("metadata"), dict) else {}
    mime = meta.get("type") if isinstance(meta.get("type"), str) else "application/octet-stream"
    user_fn = doc_rec.get("user_file_name")
    fname = user_fn if isinstance(user_fn, str) and user_fn.strip() else file_key
    return blob_bytes, mime, fname


def _object_id_or_400(value: str, *, field: str) -> ObjectId:
    try:
        return ObjectId(value)
    except InvalidId:
        raise HTTPException(status_code=400, detail=f"Invalid {field}") from None


async def _webhook_finalize_pending_uploads(
    db: Any,
    aq_client: Any,
    exec_id: str,
    trigger: dict[str, Any],
    pending: list[tuple[str, bytes, str, str | None]],
) -> dict[str, Any]:
    """Upload ``pending`` blobs to ``flow_blobs`` and merge ``binary_properties`` into ``trigger``."""

    if not pending:
        return trigger
    binary_props: list[dict[str, Any]] = []
    for i, (field, blob_bytes, mime, fname) in enumerate(pending):
        seg_f = _safe_webhook_blob_segment(field)
        seg_n = _safe_webhook_blob_segment(fname or field or "file")
        gfs_key = f"{exec_id}/webhook/incoming/{i}_{seg_f}/{seg_n}"
        await ad.mongodb.blob.save_blob_async(
            aq_client,
            bucket="flow_blobs",
            key=gfs_key,
            blob=blob_bytes,
            metadata={
                "mime_type": mime,
                "webhook_field": field,
                "file_name": fname or "",
            },
        )
        binary_props.append(
            {
                "name": field,
                "mime_type": mime,
                "file_name": fname,
                "storage_id": f"flow_blobs:{gfs_key}",
                "file_size": len(blob_bytes),
            }
        )
    merged = {**trigger, "binary_properties": binary_props}
    await db.flow_executions.update_one(
        {"_id": ObjectId(exec_id)},
        {"$set": {"trigger": merged}},
    )
    return merged


def _extract_webhook_leaf_from_nodes(nodes: list[dict[str, Any]]) -> str | None:
    """Return webhook trigger leaf if present on the revision nodes."""
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if n.get("type") != "flows.trigger.webhook":
            continue
        params = n.get("parameters") or {}
        if not isinstance(params, dict):
            return None
        leaf = params.get("webhook_leaf")
        if not isinstance(leaf, str):
            return None
        s = leaf.strip()
        return s or None
    return None


async def _upsert_flow_webhook_route_leaf(
    db: Any,
    *,
    leaf: str,
    flow_id: str,
    organization_id: str,
) -> None:
    """
    Ensure `flow_webhook_routes[_id=leaf]` is owned by this flow.

    The leaf must be system-wide unique, so if another flow already owns it,
    raise 409.
    """
    existing = await db.flow_webhook_routes.find_one({"_id": leaf})
    if existing:
        prod = existing.get("production") if isinstance(existing.get("production"), dict) else {}
        test = existing.get("test") if isinstance(existing.get("test"), dict) else {}
        owner_flow = prod.get("flow_id") or test.get("flow_id")
        if owner_flow and owner_flow != flow_id:
            raise HTTPException(status_code=409, detail="Webhook URL leaf is already in use")
    await db.flow_webhook_routes.update_one(
        {"_id": leaf},
        {
            "$setOnInsert": {"created_at": _now()},
            "$set": {
                "leaf": leaf,
                "production.flow_id": flow_id,
                "production.organization_id": organization_id,
                "updated_at": _now(),
            },
        },
        upsert=True,
    )


async def _clear_other_webhook_route_leaves_for_flow(db: Any, *, flow_id: str, keep_leaf: str) -> None:
    """If a flow changes its webhook leaf, clear old mappings for this flow."""
    cursor = db.flow_webhook_routes.find(
        {
            "_id": {"$ne": keep_leaf},
            "$or": [{"production.flow_id": flow_id}, {"test.flow_id": flow_id}],
        }
    )
    async for doc in cursor:
        old_leaf = doc.get("_id")
        if not old_leaf:
            continue
        # Unset only the parts owned by this flow.
        unset: dict[str, str] = {}
        if isinstance(doc.get("production"), dict) and doc.get("production", {}).get("flow_id") == flow_id:
            unset["production"] = ""
        if isinstance(doc.get("test"), dict) and doc.get("test", {}).get("flow_id") == flow_id:
            unset["test"] = ""
        if unset:
            await db.flow_webhook_routes.update_one(
                {"_id": old_leaf},
                {"$unset": unset, "$set": {"updated_at": _now()}},
            )


async def _remove_flow_from_webhook_routes(db: Any, *, flow_id: str) -> None:
    """Unset production/test mappings owned by ``flow_id`` and delete empty route documents."""
    cursor = db.flow_webhook_routes.find(
        {"$or": [{"production.flow_id": flow_id}, {"test.flow_id": flow_id}]}
    )
    async for doc in cursor:
        leaf = doc.get("_id")
        if not leaf:
            continue
        unset: dict[str, str] = {}
        if isinstance(doc.get("production"), dict) and doc.get("production", {}).get("flow_id") == flow_id:
            unset["production"] = ""
        if isinstance(doc.get("test"), dict) and doc.get("test", {}).get("flow_id") == flow_id:
            unset["test"] = ""
        if unset:
            await db.flow_webhook_routes.update_one(
                {"_id": leaf},
                {"$unset": unset, "$set": {"updated_at": _now()}},
            )
        leftover = await db.flow_webhook_routes.find_one({"_id": leaf})
        if leftover and not isinstance(leftover.get("production"), dict) and not isinstance(leftover.get("test"), dict):
            await db.flow_webhook_routes.delete_one({"_id": leaf})


async def _delete_execution_blobs_and_doc(db: Any, aq_client: Any, *, exec_oid: ObjectId, exec_id: str) -> None:
    await ad.mongodb.blob.delete_blobs_by_prefix_async(aq_client, bucket="flow_blobs", prefix=f"{exec_id}/")
    await db.flow_executions.delete_one({"_id": exec_oid})


_FLOW_EXECUTION_DELETE_CONCURRENCY = 8


async def _delete_flow_executions(db: Any, aq_client: Any, *, flow_id: str, organization_id: str) -> int:
    docs = await db.flow_executions.find(
        {"flow_id": flow_id, "organization_id": organization_id},
        {"_id": 1},
    ).to_list(None)
    if not docs:
        return 0

    sem = asyncio.Semaphore(_FLOW_EXECUTION_DELETE_CONCURRENCY)

    async def _delete_one(doc: dict[str, Any]) -> None:
        async with sem:
            exec_id = str(doc["_id"])
            await _delete_execution_blobs_and_doc(db, aq_client, exec_oid=doc["_id"], exec_id=exec_id)

    await asyncio.gather(*(_delete_one(doc) for doc in docs))
    return len(docs)


async def _purge_flow_associated_data(
    db: Any,
    *,
    organization_id: str,
    flow_id: str,
) -> None:
    """Remove revisions, executions, blobs, triggers, and other rows tied to one flow."""
    aq_client = ad.common.get_analytiq_client()

    trigger_svc = ad.flows.get_flow_trigger_service()
    if trigger_svc is not None:
        await trigger_svc.deregister_flow(flow_id)
    else:
        await ad.flows.delete_trigger_registrations(db, flow_id=flow_id)

    await ad.docrouter_flows.event_dispatch.delete_docrouter_flow_triggers(db, flow_id=flow_id)
    await ad.docrouter_flows.delete_flow_results_for_flow(db, flow_id=flow_id)
    await _remove_flow_from_webhook_routes(db, flow_id=flow_id)

    n_exec = await _delete_flow_executions(db, aq_client, flow_id=flow_id, organization_id=organization_id)
    if n_exec:
        logger.info(f"Flow delete removed {n_exec} execution(s) for flow_id={flow_id}")

    await db.flow_static_data.delete_many({"flow_id": flow_id})
    await db.flow_trigger_leases.delete_many({"flow_id": flow_id})

    rev_docs = await db.flow_revisions.find({"flow_id": flow_id}, {"_id": 1}).to_list(None)
    rev_ids = [str(d["_id"]) for d in rev_docs]
    try:
        n_pins = await ad.mongodb.blob.delete_flow_pins_for_flow_async(
            aq_client,
            organization_id=organization_id,
            flow_id=flow_id,
            flow_revision_ids=rev_ids,
        )
        if n_pins:
            logger.info(f"Flow delete removed {n_pins} flow_pins blob(s) for flow_id={flow_id}")
    except Exception:
        logger.warning(f"Flow delete: failed flow_pins sweep for flow_id={flow_id}", exc_info=True)

    await db.flow_revisions.delete_many({"flow_id": flow_id})


def _raise_if_run_data_entries_oversized(run_data: dict[str, Any]) -> None:
    for nid, entry in run_data.items():
        try:
            blob = json.dumps(entry, default=str).encode("utf-8")
        except TypeError:
            blob = repr(entry).encode("utf-8")
        if len(blob) > _MAX_PREVIEW_RUN_DATA_ENTRY_BYTES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"run_data entry for node {nid!r} exceeds maximum size "
                    f"({_MAX_PREVIEW_RUN_DATA_ENTRY_BYTES} bytes) for preview"
                ),
            )


class FlowHeader(BaseModel):
    flow_id: str
    organization_id: str
    name: str
    active: bool
    active_flow_revid: Optional[str] = None
    flow_version: int
    callable_as_tool: bool = False
    tool_description: str | None = None
    tool_schema: dict[str, Any] | None = None
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: str


def _flow_header_dict(h: dict[str, Any], *, flow_id: str) -> dict[str, Any]:
    created_at = h["created_at"]
    updated_at = h["updated_at"]
    return {
        "flow_id": flow_id,
        "organization_id": h["organization_id"],
        "name": h["name"],
        "active": bool(h.get("active")),
        "active_flow_revid": h.get("active_flow_revid"),
        "flow_version": int(h.get("flow_version") or 0),
        "callable_as_tool": bool(h.get("callable_as_tool")),
        "tool_description": h.get("tool_description"),
        "tool_schema": h.get("tool_schema"),
        "created_at": created_at.replace(tzinfo=UTC) if isinstance(created_at, datetime) else created_at,
        "created_by": h["created_by"],
        "updated_at": updated_at.replace(tzinfo=UTC) if isinstance(updated_at, datetime) else updated_at,
        "updated_by": h["updated_by"],
    }


class FlowRevision(BaseModel):
    flow_revid: str
    flow_id: str
    flow_version: int
    nodes: list[dict[str, Any]]
    connections: dict[str, Any]
    settings: dict[str, Any] = {}
    pin_data: dict[str, Any] | None = None
    graph_hash: str
    engine_version: int = 1
    created_at: datetime
    created_by: str


class CreateFlowRequest(BaseModel):
    """Create a flow header. When ``nodes`` is set, also persist the first revision in the same request."""

    name: str
    nodes: list[dict[str, Any]] | None = None
    connections: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None
    pin_data: dict[str, Any] | None = None


class CreateFlowResponse(BaseModel):
    flow: FlowHeader
    revision: FlowRevision | None = None


class ListFlowsResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int


class FlowDocumentResult(BaseModel):
    flow_id: str
    flow_name: str
    flow_revid: str | None = None
    flow_version: int | None = None
    document_id: str
    execution_id: str = ""
    event_type: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PatchFlowRequest(BaseModel):
    name: str | None = None
    callable_as_tool: bool | None = None
    tool_description: str | None = None
    tool_schema: dict[str, Any] | None = None


class SaveFlowRequest(BaseModel):
    base_flow_revid: str
    name: str
    nodes: list[dict[str, Any]]
    connections: dict[str, Any]
    settings: dict[str, Any] = {}
    pin_data: dict[str, Any] | None = None


class SaveFlowResponse(BaseModel):
    flow: FlowHeader
    revision: FlowRevision | None = None


class ListenWebhookTestRequest(BaseModel):
    webhook_leaf: str | None = None
    revision_snapshot: FlowRevisionSnapshotRequest


class ListenWebhookTestResponse(BaseModel):
    webhook_leaf: str
    test_path: str
    production_path: str


class StopWebhookTestRequest(BaseModel):
    """Optional hints for tearing down `/webhook-test/{leaf}` without requiring a snapshot."""

    webhook_leaf: str | None = None
    revision_snapshot: FlowRevisionSnapshotRequest | None = None


class ScheduleTriggerTestRequest(BaseModel):
    revision_snapshot: FlowRevisionSnapshotRequest
    trigger_node_id: str | None = Field(
        None,
        description="Schedule trigger node id; required when the graph has multiple schedule triggers.",
    )


class ScheduleTriggerTestResponse(BaseModel):
    execution_id: str


class PollTriggerTestRequest(BaseModel):
    revision_snapshot: FlowRevisionSnapshotRequest
    trigger_node_id: str | None = Field(
        None,
        description="Poll trigger node id; required when the graph has multiple poll triggers.",
    )


class ActivateFlowRequest(BaseModel):
    flow_revid: str | None = None


class FlowRevisionSnapshotRequest(BaseModel):
    """Immutable graph copied from the editor for an unsaved execute request (`/run`)."""
    nodes: list[dict[str, Any]]
    connections: dict[str, Any]
    settings: dict[str, Any] = Field(default_factory=dict)
    pin_data: dict[str, Any] | None = None


class ToolTestRequest(BaseModel):
    """Path B: execute-step on a tool_provider with synthetic Tool Executor rewire."""

    tool_name: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class RunFlowRequest(BaseModel):
    flow_revid: str | None = Field(None, description="Revision lineage id for the execution; optional when revision_snapshot is supplied.")
    start_trigger_node_id: str | None = Field(
        None,
        description="When the revision has multiple triggers, which one starts a full run (required in that case). For execute-step runs the engine infers the trigger when omitted if unambiguous.",
    )
    target_node_id: str | None = Field(
        None,
        description="Execute-step: run through this node only (upstream closure). Prior outputs may be supplied via run_data.",
    )
    run_data: dict[str, Any] | None = Field(
        None,
        description="Per-node output seed keyed by node id (validated). Used with target_node_id for execute-step.",
    )
    dirty_node_ids: list[str] | None = Field(
        None,
        description="Node ids whose seed entries are ignored so those nodes re-execute.",
    )
    revision_snapshot: FlowRevisionSnapshotRequest | None = Field(
        None,
        description="Immutable editor graph for an immediate run; overrides the stored revision when set.",
    )
    tool_test_request: ToolTestRequest | None = Field(
        None,
        description="Path B tool test: rewire graph with synthetic manual trigger + Tool Executor for this run.",
    )


async def _resolve_flow_revid_lineage(flow_id: str, flow_revid: str | None, db: Any) -> str:
    """Return `flow_revid` only if it is a valid revision id on this flow; else empty (e.g. never saved yet)."""

    fid = (flow_revid or "").strip()
    if not fid:
        return ""
    try:
        oid = ObjectId(fid)
    except Exception:
        return ""
    doc = await db.flow_revisions.find_one({"_id": oid, "flow_id": flow_id})
    return fid if doc else ""


class FlowExecution(BaseModel):
    model_config = ConfigDict(extra="ignore")

    execution_id: str
    flow_id: str
    flow_revid: str
    organization_id: str
    mode: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    stop_requested: bool = False
    last_node_executed: str | None = None
    run_data: dict[str, Any] = {}
    error: dict[str, Any] | None = None
    trigger: dict[str, Any]
    start_trigger_node_id: str | None = None
    target_node_id: str | None = None
    initial_run_data: dict[str, Any] | None = None
    completed_nodes: list[str] = []
    resumed_from: str | None = None
    resumed_by: str | None = None
    #: Present on list responses when joined from ``flows`` (org-wide execution views).
    flow_name: str | None = None


class ListExecutionsResponse(BaseModel):
    items: list[FlowExecution]
    total: int


class PreviewFlowExpressionRequest(BaseModel):
    expression: str = Field(..., max_length=16_384)
    run_data: dict[str, Any] = Field(default_factory=dict)
    """Plain JSON rows for inbound slot 0 (same shape as INPUT tab / ``itemsJson`` previews)."""

    input_items: list[dict[str, Any]] = Field(default_factory=list)
    preview_item_index: int = Field(0, ge=0, le=50_000)
    execution_refs: dict[str, Any] | None = None
    """Revision ``nodes`` for name-keyed ``_node`` in expressions (same shape as flow revision nodes)."""

    nodes: list[dict[str, Any]] = Field(default_factory=list)


class PreviewFlowExpressionResponse(BaseModel):
    skipped: bool = False
    ok: bool
    preview_text: str | None = None
    value: Any | None = None
    error: str | None = None


async def _get_db():
    return ad.common.get_async_db()


def _execution_doc_to_list_item(d: dict[str, Any]) -> FlowExecution:
    """Serialize a `flow_executions` document for list responses (ISO timestamps for JSON)."""

    fn = d.get("flow_name")
    return FlowExecution(
        execution_id=str(d["_id"]),
        flow_id=d["flow_id"],
        flow_revid=d["flow_revid"],
        organization_id=d["organization_id"],
        mode=d["mode"],
        status=d["status"],
        started_at=(
            d["started_at"].replace(tzinfo=UTC).isoformat()
            if isinstance(d.get("started_at"), datetime)
            else None
        ),
        finished_at=(
            d["finished_at"].replace(tzinfo=UTC).isoformat()
            if isinstance(d.get("finished_at"), datetime)
            else d.get("finished_at")
        ),
        last_heartbeat_at=(
            d["last_heartbeat_at"].replace(tzinfo=UTC).isoformat()
            if isinstance(d.get("last_heartbeat_at"), datetime)
            else d.get("last_heartbeat_at")
        ),
        stop_requested=bool(d.get("stop_requested")),
        last_node_executed=d.get("last_node_executed"),
        run_data=d.get("run_data") or {},
        error=d.get("error"),
        trigger=d.get("trigger") or {},
        target_node_id=d.get("target_node_id"),
        initial_run_data=d.get("initial_run_data"),
        completed_nodes=[str(x) for x in (d.get("completed_nodes") or []) if x],
        resumed_from=str(d["resumed_from"]) if d.get("resumed_from") else None,
        resumed_by=str(d["resumed_by"]) if d.get("resumed_by") else None,
        flow_name=str(fn) if fn is not None else None,
    )


def _now() -> datetime:
    return datetime.now(UTC)


async def _org_experimental_features_enabled(db, organization_id: str) -> bool:
    from bson import ObjectId

    try:
        oid = ObjectId(organization_id)
    except Exception:
        return False
    doc = await db.organizations.find_one({"_id": oid}, {"experimental_features": 1})
    if not doc:
        return False
    return bool(doc.get("experimental_features"))


@flows_router.get("/v0/orgs/{organization_id}/flows/node-types")
async def list_node_types(organization_id: str, current_user: User = Depends(get_org_user)):
    # Node types are global; org is for auth scoping and experimental gating.
    db = await _get_db()
    show_exp = await _org_experimental_features_enabled(db, organization_id)
    items = []
    for entry in ad.flows.list_palette_entries():
        if entry.get("experimental") and not show_exp:
            continue
        items.append(entry)
    return {"items": items, "total": len(items)}


@flows_router.post(
    "/v0/orgs/{organization_id}/flows/preview-expression",
    response_model=PreviewFlowExpressionResponse,
)
async def preview_flow_expression(
    organization_id: str,
    req: PreviewFlowExpressionRequest,
    current_user: User = Depends(get_org_user),
):
    # Auth only (org scoped); evaluator is sandboxed in analytiq_data.
    if len(req.run_data) > 120:
        raise HTTPException(status_code=400, detail="run_data has too many node entries for preview")
    if len(req.nodes) > 400:
        raise HTTPException(status_code=400, detail="nodes list is too large for preview")
    _raise_if_run_data_entries_oversized(req.run_data)

    val, err = ad.flows.preview_parameter_expression(
        req.expression,
        run_data=req.run_data,
        input_items_json=req.input_items,
        preview_item_index=req.preview_item_index,
        execution_refs=req.execution_refs,
        revision_nodes=req.nodes,
    )
    if val is None and err is None:
        return PreviewFlowExpressionResponse(skipped=True, ok=True)

    if err is not None:
        return PreviewFlowExpressionResponse(skipped=False, ok=False, error=err)

    preview_body: str
    try:
        preview_body = json.dumps(val, default=str)
    except TypeError:
        preview_body = str(val)
    max_len = 4000
    if len(preview_body) > max_len:
        preview_body = f"{preview_body[:max_len]}…"

    return PreviewFlowExpressionResponse(skipped=False, ok=True, preview_text=preview_body, value=val)


@flows_router.post("/v0/orgs/{organization_id}/flows", response_model=CreateFlowResponse)
async def create_flow(organization_id: str, req: CreateFlowRequest, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    created_at = _now()
    res = await db.flows.insert_one(
        {
            "organization_id": organization_id,
            "name": req.name,
            "active": False,
            "active_flow_revid": None,
            "flow_version": 0,
            "created_at": created_at,
            "created_by": current_user.user_id,
            "updated_at": created_at,
            "updated_by": current_user.user_id,
        }
    )
    flow_id = str(res.inserted_id)
    if req.nodes is None:
        header = await db.flows.find_one({"_id": ObjectId(flow_id)})
        _raw = {k: header[k] for k in header if k != "_id"}
        hdr = {k: (v.replace(tzinfo=UTC) if isinstance(v, datetime) else v) for k, v in _raw.items()}
        return {"flow": FlowHeader(flow_id=flow_id, **hdr), "revision": None}

    connections = req.connections if req.connections is not None else {}
    settings_payload = req.settings if req.settings is not None else {}
    # First revision: latest is None, so save_revision's base check is skipped; empty string is valid.
    save_req = SaveFlowRequest(
        base_flow_revid="",
        name=req.name,
        nodes=req.nodes,
        connections=connections,
        settings=settings_payload,
        pin_data=req.pin_data,
    )
    try:
        saved = await save_revision(organization_id, flow_id, save_req, current_user)
        return {"flow": saved["flow"], "revision": saved["revision"]}
    except Exception:
        await db.flow_revisions.delete_many({"flow_id": flow_id})
        await db.flows.delete_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
        raise


_LOOKUP_LATEST_REVISION = {
    "$lookup": {
        "from": "flow_revisions",
        "let": {"fid": {"$toString": "$_id"}},
        "pipeline": [
            {"$match": {"$expr": {"$eq": ["$flow_id", "$$fid"]}}},
            {"$sort": {"flow_version": -1}},
            {"$limit": 1},
            {"$project": {"_id": 1, "flow_version": 1, "graph_hash": 1}},
        ],
        "as": "_latest",
    }
}


_MATCH_HAS_SAVED_REVISION = {"$match": {"$expr": {"$gt": [{"$size": "$_latest"}, 0]}}}


@flows_router.get("/v0/orgs/{organization_id}/flows", response_model=ListFlowsResponse)
async def list_flows(
    organization_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    document_id: str | None = Query(
        None,
        description="When set, return flows whose document-event trigger matches this document's tags.",
    ),
    callable_as_tool: bool | None = Query(
        None,
        description="When set, filter flows by callable_as_tool metadata.",
    ),
    active_only: bool = Query(
        False,
        description="When true, return only active flows (useful for flow pickers).",
    ),
    include_unsaved: bool = Query(
        False,
        description="If true, include flow headers that have no saved revision (draft-only).",
    ),
    current_user: User = Depends(get_org_user),
):
    _ = current_user
    db = await _get_db()
    if document_id:
        try:
            items, total = await list_matching_flows_for_document(
                db,
                org_id=organization_id,
                document_id=document_id,
                limit=limit,
                offset=offset,
            )
        except ValueError:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"items": items, "total": total}

    match: dict[str, Any] = {"organization_id": organization_id}
    if callable_as_tool is not None:
        match["callable_as_tool"] = callable_as_tool
    if active_only:
        match["active"] = True

    base_stages: list[dict[str, Any]] = [
        {"$match": match},
        {"$sort": {"updated_at": -1}},
        _LOOKUP_LATEST_REVISION,
    ]
    if not include_unsaved:
        base_stages.append(_MATCH_HAS_SAVED_REVISION)
    count_rows = await db.flows.aggregate(base_stages + [{"$count": "total"}]).to_list(1)
    total = int(count_rows[0]["total"]) if count_rows else 0
    pipeline = base_stages + [{"$skip": offset}, {"$limit": limit}]
    rows = await db.flows.aggregate(pipeline).to_list(limit)
    items: list[dict[str, Any]] = []
    for h in rows:
        fid = str(h["_id"])
        latest = h["_latest"][0] if h.get("_latest") else None
        header = _flow_header_dict(h, flow_id=fid)
        items.append(
            {
                "flow": {
                    **header,
                    "created_at": header["created_at"].replace(tzinfo=UTC).isoformat()
                    if isinstance(header["created_at"], datetime)
                    else header["created_at"],
                    "updated_at": header["updated_at"].replace(tzinfo=UTC).isoformat()
                    if isinstance(header["updated_at"], datetime)
                    else header["updated_at"],
                },
                "latest_revision": None if not latest else {
                    "flow_revid": str(latest["_id"]),
                    "flow_version": latest["flow_version"],
                    "graph_hash": latest.get("graph_hash"),
                },
            }
        )
    return {"items": items, "total": total}


@flows_router.get(
    "/v0/orgs/{organization_id}/flows/result/{document_id}",
    response_model=FlowDocumentResult,
)
async def get_flow_document_result(
    organization_id: str,
    document_id: str,
    flow_id: str | None = Query(None, description="Stable flow id"),
    flow_revid: str | None = Query(None, description="Flow revision id (resolves flow_id when omitted)"),
    current_user: User = Depends(get_org_user),
):
    """Retrieve the captured flow result for a document (mirrors ``GET .../llm/result/{document_id}``)."""
    _ = current_user
    if not (flow_id or "").strip() and not (flow_revid or "").strip():
        raise HTTPException(status_code=400, detail="flow_id or flow_revid is required")
    db = await _get_db()
    try:
        row = await get_document_flow_result(
            db,
            org_id=organization_id,
            document_id=document_id,
            flow_id=(flow_id or "").strip() or None,
            flow_revid=(flow_revid or "").strip() or None,
        )
    except ValueError as exc:
        msg = str(exc)
        if msg == "Document not found":
            raise HTTPException(status_code=404, detail=msg)
        if msg == "Flow not found":
            raise HTTPException(status_code=404, detail=msg)
        if msg in {"Flow revision not found", "Flow does not match document", "Flow result not found"}:
            raise HTTPException(status_code=404, detail=msg)
        if msg == "flow_id or flow_revid is required":
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return FlowDocumentResult(**row)


class BulkAnalyzeFlowsDocumentFilters(BaseModel):
    tag_ids: Optional[List[str]] = None
    name_search: Optional[str] = None
    metadata_search: Optional[dict[str, str]] = None
    filters: Optional[dict[str, Any]] = None


class BulkAnalyzeFlowsRequest(BaseModel):
    mode: Literal["all", "missing", "outdated"]
    tag_id: Optional[str] = None
    flow_ids: Optional[List[str]] = None
    document_filters: BulkAnalyzeFlowsDocumentFilters = Field(default_factory=BulkAnalyzeFlowsDocumentFilters)


class BulkAnalyzeFlowsExecutionItem(BaseModel):
    document_id: str
    document_name: str
    reason: Optional[Literal["missing", "outdated", "forced"]] = None


class BulkAnalyzeFlowsGroup(BaseModel):
    flow_id: str
    flow_name: str
    flow_version: int
    trigger_type: Literal["docrouter.trigger"] = "docrouter.trigger"
    event_type: Optional[str] = None
    executions: List[BulkAnalyzeFlowsExecutionItem]


class BulkAnalyzeFlowsResponse(BaseModel):
    total_executions: int
    groups: List[BulkAnalyzeFlowsGroup]


@flows_router.post(
    "/v0/orgs/{organization_id}/flows/bulk-analyze",
    response_model=BulkAnalyzeFlowsResponse,
)
async def bulk_analyze_flows(
    organization_id: str,
    request: BulkAnalyzeFlowsRequest = Body(...),
    current_user: User = Depends(get_org_user),
):
    """Analyze which document-flow pairs need re-run for bulk Run Flows."""
    _ = current_user
    logger.info(
        f"bulk_analyze_flows(): org={organization_id} tag_id={request.tag_id} mode={request.mode}"
    )
    filters = request.document_filters
    try:
        result = await bulk_analyze_flow_executions(
            ad.common.get_analytiq_client(),
            organization_id,
            request.mode,
            tag_id=request.tag_id,
            flow_ids=request.flow_ids,
            tag_ids=filters.tag_ids,
            name_search=filters.name_search,
            metadata_search=filters.metadata_search,
            filter_model=filters.filters,
        )
    except ValueError as exc:
        if str(exc) == "tag_id or flow_ids is required":
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BulkAnalyzeFlowsResponse(**result)


class RerunFlowForDocumentRequest(BaseModel):
    mode: Literal["force", "incomplete_only"] = "force"


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/run/{document_id}")
async def rerun_flow_for_document_route(
    organization_id: str,
    flow_id: str,
    document_id: str,
    body: RerunFlowForDocumentRequest = Body(default_factory=RerunFlowForDocumentRequest),
    current_user: User = Depends(get_org_user),
):
    """Re-run an active document-event flow for a document (mirrors prompt reload on the Extraction tab)."""
    _ = current_user
    try:
        execution_id = await rerun_flow_for_document(
            ad.common.get_analytiq_client(),
            org_id=organization_id,
            document_id=document_id,
            flow_id=flow_id,
            mode=body.mode,
        )
    except ValueError as exc:
        msg = str(exc)
        if msg in {"Document not found", "Flow not found", "Flow revision not found", "Trigger node not found", "Flow result not found"}:
            raise HTTPException(status_code=404, detail=msg) from exc
        if msg in {"Flow is not active", "Flow has no active revision", "Flow does not match document"}:
            raise HTTPException(status_code=400, detail=msg) from exc
        if msg in {"No partial execution to resume", "Flow revision changed; use force rerun"}:
            raise HTTPException(status_code=409, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    return {"execution_id": execution_id}


@flows_router.get("/v0/orgs/{organization_id}/flows/{flow_id}")
async def get_flow(organization_id: str, flow_id: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    latest = await db.flow_revisions.find_one({"flow_id": flow_id}, sort=[("flow_version", -1)])
    return {
        "flow": _flow_header_dict(h, flow_id=flow_id),
        "latest_revision": None if not latest else {"flow_revid": str(latest["_id"]), "flow_version": latest["flow_version"], "graph_hash": latest.get("graph_hash")},
    }


@flows_router.patch("/v0/orgs/{organization_id}/flows/{flow_id}")
async def patch_flow_metadata(
    organization_id: str, flow_id: str, req: PatchFlowRequest, current_user: User = Depends(get_org_user)
):
    db = await _get_db()
    has_field_updates = (
        req.name is not None
        or req.callable_as_tool is not None
        or req.tool_description is not None
        or req.tool_schema is not None
    )
    if not has_field_updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates: dict[str, Any] = {"updated_at": _now(), "updated_by": current_user.user_id}
    if req.name is not None:
        updates["name"] = req.name
    if req.callable_as_tool is not None:
        updates["callable_as_tool"] = req.callable_as_tool
    if req.tool_description is not None:
        updates["tool_description"] = req.tool_description
    if req.tool_schema is not None:
        updates["tool_schema"] = req.tool_schema

    if req.callable_as_tool:
        from analytiq_data.flows.callable_flow import validate_callable_flow_revision

        latest = await db.flow_revisions.find_one({"flow_id": flow_id}, sort=[("flow_version", -1)])
        if latest:
            try:
                validate_callable_flow_revision(latest.get("nodes") or [])
            except ad.flows.FlowValidationError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e

    res = await db.flows.update_one(
        {"_id": ObjectId(flow_id), "organization_id": organization_id},
        {"$set": updates},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Flow not found")
    return await get_flow(organization_id, flow_id, current_user)


@flows_router.delete("/v0/orgs/{organization_id}/flows/{flow_id}")
async def delete_flow(organization_id: str, flow_id: str, current_user: User = Depends(get_org_user)):
    """Delete a flow and all associated revisions, executions, blobs, and trigger registrations."""

    _ = current_user
    db = await _get_db()
    hdr = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not hdr:
        raise HTTPException(status_code=404, detail="Flow not found")

    from analytiq_data.flows.flow_references import find_flows_referencing_target, format_flow_delete_blocked_message

    refs = await find_flows_referencing_target(db, organization_id=organization_id, target_flow_id=flow_id)
    if refs:
        raise HTTPException(status_code=409, detail=format_flow_delete_blocked_message(refs))

    await _purge_flow_associated_data(db, organization_id=organization_id, flow_id=flow_id)

    res = await db.flows.delete_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Flow not found")
    return {"ok": True}


@flows_router.get("/v0/orgs/{organization_id}/flows/{flow_id}/revisions")
async def list_revisions(
    organization_id: str,
    flow_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_org_user),
):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    total = await db.flow_revisions.count_documents({"flow_id": flow_id})
    revs = await db.flow_revisions.find({"flow_id": flow_id}).sort([("flow_version", -1)]).skip(offset).limit(limit).to_list(limit)
    items = []
    for r in revs:
        items.append(
            {
                "flow_revid": str(r["_id"]),
                "flow_version": r["flow_version"],
                "graph_hash": r.get("graph_hash"),
                "created_at": r["created_at"].replace(tzinfo=UTC).isoformat()
                if isinstance(r["created_at"], datetime)
                else r["created_at"],
                "created_by": r["created_by"],
            }
        )
    return {"items": items, "total": total}


@flows_router.get("/v0/orgs/{organization_id}/flows/{flow_id}/revisions/{flow_revid}")
async def get_revision(organization_id: str, flow_id: str, flow_revid: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    r = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid), "flow_id": flow_id})
    if not r:
        raise HTTPException(status_code=404, detail="Revision not found")
    out = {**r, "_id": str(r["_id"])}
    for k, v in list(out.items()):
        if isinstance(v, datetime):
            out[k] = v.replace(tzinfo=UTC)
    return out


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/revisions/{flow_revid}/pins/binary")
async def upload_pinned_binary(
    organization_id: str,
    flow_id: str,
    flow_revid: str,
    node_id: str = Form(..., min_length=1),
    slot: int = Form(0, ge=0),
    item_index: int = Form(..., ge=0),
    property: str = Form(..., min_length=1),
    file: UploadFile = File(...),
    current_user: User = Depends(get_org_user),
):
    """
    Upload one pinned binary attachment for a revision pin_data payload.

    Returns a `FlowBinaryRef`-shaped dict for embedding into `pin_data`.

    Orphan caveat: blobs are keyed under this revision id. They are garbage-collected when a saved
    pin_data stops referencing them (on a later revision save). Uploads made before pin_data is
    saved, or uploads that are never referenced, are not cleaned up automatically (no TTL yet).
    """

    _ = current_user
    db = await _get_db()
    flow_oid = _object_id_or_400(flow_id, field="flow_id")
    rev_oid = _object_id_or_400(flow_revid, field="flow_revid")
    h = await db.flows.find_one({"_id": flow_oid, "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    r = await db.flow_revisions.find_one({"_id": rev_oid, "flow_id": flow_id})
    if not r:
        raise HTTPException(status_code=404, detail="Revision not found")

    if not node_id.strip():
        raise HTTPException(status_code=400, detail="node_id is required")
    prop = property.strip()
    if not prop:
        raise HTTPException(status_code=400, detail="property is required")

    fname = (file.filename or "").strip() or "file"
    seg_node = _safe_webhook_blob_segment(node_id.strip())
    seg_prop = _safe_webhook_blob_segment(prop)
    seg_name = _safe_webhook_blob_segment(fname)
    key = f"pin/{flow_revid}/{seg_node}/{int(slot)}/{int(item_index)}/{seg_prop}/{seg_name}"

    blob = await file.read(MAX_PIN_UPLOAD_BYTES + 1)
    if len(blob) > MAX_PIN_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_PIN_UPLOAD_BYTES} bytes)",
        )

    mime = (file.content_type or "").strip() or "application/octet-stream"
    aq_client = ad.common.get_analytiq_client()
    await ad.mongodb.blob.save_blob_async(
        aq_client,
        bucket="flow_pins",
        key=key,
        blob=blob,
        metadata={
            "mime_type": mime,
            "file_name": fname,
            "organization_id": organization_id,
            "flow_id": flow_id,
            "flow_revid": flow_revid,
            "node_id": node_id,
            "slot": int(slot),
            "item_index": int(item_index),
            "property": prop,
        },
    )

    return {
        "mime_type": mime,
        "file_name": fname,
        "storage_id": f"flow_pins:{key}",
        "file_size": len(blob),
    }


@flows_router.get("/v0/orgs/{organization_id}/flows/{flow_id}/revisions/{flow_revid}/pins/blob")
async def get_revision_pin_blob(
    organization_id: str,
    flow_id: str,
    flow_revid: str,
    storage_id: str = Query(
        ...,
        min_length=1,
        description=(
            "FlowBinaryRef.storage_id: flow_pins:pin/<flowRevid>/… or files:<gridfs-key> "
            "(org document ownership verified)."
        ),
    ),
    action: Literal["view", "download"] = Query(
        "download",
        description=(
            "`view`: inline preview only for image/* (excluding SVG) and PDF; other types use attachment. "
            "`download`: attachment."
        ),
    ),
    current_user: User = Depends(get_org_user),
):
    """Return bytes for a pinned binary (`flow_pins`) or org document file (`files:`) scoped to this revision."""

    _ = current_user
    db = await _get_db()
    flow_oid = _object_id_or_400(flow_id, field="flow_id")
    rev_oid = _object_id_or_400(flow_revid, field="flow_revid")
    h = await db.flows.find_one({"_id": flow_oid, "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    r = await db.flow_revisions.find_one({"_id": rev_oid, "flow_id": flow_id})
    if not r:
        raise HTTPException(status_code=404, detail="Revision not found")

    sid = storage_id.strip()
    parts = sid.split(":", 1)
    if len(parts) != 2 or not parts[1]:
        raise HTTPException(status_code=400, detail="Invalid storage_id")
    bucket, key = parts[0], parts[1]

    aq_client = ad.common.get_analytiq_client()

    if bucket == "flow_pins":
        await _require_flow_pins_key_for_revision(db, flow_id=flow_id, flow_revid=flow_revid, key=key)
        result = await ad.mongodb.blob.get_blob_async(aq_client, bucket="flow_pins", key=key)
        blob = _gridfs_blob_bytes(result)
        mime, fname = _gridfs_meta_mime_and_filename(result.get("metadata"))
        return _binary_blob_http_response(blob=blob, mime=mime, file_name=fname, action=action)

    if bucket == "files":
        blob, mime, fname = await _load_org_document_file_blob(
            db, aq_client, organization_id=organization_id, file_key=key
        )
        return _binary_blob_http_response(blob=blob, mime=mime, file_name=fname, action=action)

    raise HTTPException(status_code=400, detail="Invalid storage_id")


@flows_router.put("/v0/orgs/{organization_id}/flows/{flow_id}", response_model=SaveFlowResponse)
async def save_revision(organization_id: str, flow_id: str, req: SaveFlowRequest, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")

    latest = await db.flow_revisions.find_one({"flow_id": flow_id}, sort=[("flow_version", -1)])
    if latest and str(latest["_id"]) != req.base_flow_revid:
        raise HTTPException(status_code=409, detail="base_flow_revid is not the latest revision")

    nodes = req.nodes
    try:
        connections = ad.flows.coerce_json_connections_to_dataclasses(req.connections)
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid connections: {e}") from e
    settings = req.settings or {}
    pin_data = req.pin_data

    try:
        ad.flows.validate_revision(nodes, connections, settings, pin_data)
    except ad.flows.FlowValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        ad.docrouter_flows.event_dispatch.validate_docrouter_trigger_params(
            {
                "nodes": nodes,
                "connections": req.connections,
                "settings": settings,
                "pin_data": pin_data,
            }
        )
    except ad.flows.FlowValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Ensure webhook trigger leaf is persisted and system-wide unique (if this graph uses webhook trigger).
    leaf = _extract_webhook_leaf_from_nodes(nodes)
    if leaf is None:
        # If the trigger exists but leaf is missing, generate one so the editor always gets URLs.
        if any(isinstance(n, dict) and n.get("type") == "flows.trigger.webhook" for n in nodes):
            leaf = str(uuid4())
            for n in nodes:
                if isinstance(n, dict) and n.get("type") == "flows.trigger.webhook":
                    p = n.get("parameters")
                    if not isinstance(p, dict):
                        n["parameters"] = {"webhook_leaf": leaf}
                    else:
                        p.setdefault("webhook_leaf", leaf)
                    break
    if leaf:
        await _upsert_flow_webhook_route_leaf(db, leaf=leaf, flow_id=flow_id, organization_id=organization_id)
        await _clear_other_webhook_route_leaves_for_flow(db, flow_id=flow_id, keep_leaf=leaf)

    # Pin binary cleanup: delete `flow_pins` blobs that were referenced by the superseded revision's
    # pin_data but are not referenced by the incoming pin_data.
    #
    # Blob keys are ``pin/{flow_revid_at_upload}/…``; that segment is the revision head at upload time,
    # not necessarily the revision row that last held the pin. Matching only ``pin/{latest_id}/`` would
    # miss stale keys (e.g. pin uploaded under R1, pin_data carried on R2+). Use prefix ``pin/`` so any
    # key present in the flow's stored prev pin_data set is eligible for removal when dropped.
    if latest is not None and latest.get("_id"):
        prev_keys = _flow_pins_keys_from_pin_data(latest.get("pin_data"), prefix="pin/")
        next_keys = _flow_pins_keys_from_pin_data(pin_data, prefix="pin/")
        removed = sorted(prev_keys - next_keys)
        if removed:
            aq_client = ad.common.get_analytiq_client()
            for key in removed:
                try:
                    await ad.mongodb.blob.delete_blob_async(aq_client, bucket="flow_pins", key=key)
                except Exception:
                    # Best-effort cleanup; never block flow saves.
                    logger.warning(f"Failed deleting flow_pins blob {key!r} during pin cleanup", exc_info=True)

    ghash = ad.flows.canonical_graph_hash(nodes, req.connections, settings)

    def _stable_pin_json(p: Any) -> str:
        return json.dumps(p, sort_keys=True, separators=(",", ":"), default=str)

    pin_same = latest is not None and _stable_pin_json(latest.get("pin_data")) == _stable_pin_json(pin_data)

    def _semantic_graph_unchanged() -> bool:
        if latest is None:
            return False
        if latest.get("graph_hash") == ghash:
            return True
        return (
            ad.flows.canonical_graph_hash(
                latest.get("nodes") or [],
                latest.get("connections") or {},
                latest.get("settings") or {},
            )
            == ghash
        )

    # graph_hash excludes pin_data, node position, and display names; require matching pin_data so pin-only edits still persist.
    if _semantic_graph_unchanged() and pin_same:
        now = _now()
        header_updates: dict[str, Any] = {}
        if req.name != h.get("name"):
            header_updates = {"name": req.name, "updated_at": now, "updated_by": current_user.user_id}
        stored_nodes = latest.get("nodes") or []
        if stored_nodes != nodes:
            await db.flow_revisions.update_one(
                {"_id": latest["_id"]},
                {"$set": {"nodes": nodes}},
            )
            if not header_updates:
                header_updates = {"updated_at": now, "updated_by": current_user.user_id}
        if header_updates:
            await db.flows.update_one(
                {"_id": ObjectId(flow_id)},
                {"$set": header_updates},
            )
        h2 = await db.flows.find_one({"_id": ObjectId(flow_id)})
        _raw = {k: h2[k] for k in h2 if k != "_id"}
        hdr = {k: (v.replace(tzinfo=UTC) if isinstance(v, datetime) else v) for k, v in _raw.items()}
        return {
            "flow": FlowHeader(flow_id=flow_id, **hdr),
            "revision": None,
        }

    next_version = int(h.get("flow_version") or 0) + 1
    created_at = _now()
    res = await db.flow_revisions.insert_one(
        {
            "flow_id": flow_id,
            "flow_version": next_version,
            "nodes": nodes,
            "connections": req.connections,  # store JSON-friendly shape
            "settings": settings,
            "pin_data": pin_data,
            "graph_hash": ghash,
            "engine_version": 1,
            "created_at": created_at,
            "created_by": current_user.user_id,
        }
    )
    flow_revid = str(res.inserted_id)
    flow_header_set: dict[str, Any] = {
        "name": req.name,
        "flow_version": next_version,
        "updated_at": created_at,
        "updated_by": current_user.user_id,
    }
    if h.get("active"):
        flow_header_set["active_flow_revid"] = flow_revid
    await db.flows.update_one(
        {"_id": ObjectId(flow_id)},
        {"$set": flow_header_set},
    )
    h2 = await db.flows.find_one({"_id": ObjectId(flow_id)})
    r = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid)})
    if h.get("active"):
        try:
            await ad.docrouter_flows.event_dispatch.sync_docrouter_flow_triggers(
                db,
                org_id=organization_id,
                flow_id=flow_id,
                flow_revid=flow_revid,
                revision=r,
            )
        except ad.flows.FlowValidationError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        trigger_svc = ad.flows.get_flow_trigger_service()
        if trigger_svc is not None:
            await trigger_svc.register_flow(
                organization_id,
                flow_id,
                flow_revid,
                r,
                run_immediately=True,
            )
    _raw = {k: h2[k] for k in h2 if k != "_id"}
    hdr = {k: (v.replace(tzinfo=UTC) if isinstance(v, datetime) else v) for k, v in _raw.items()}
    rev = FlowRevision(
        flow_revid=flow_revid,
        flow_id=flow_id,
        flow_version=r["flow_version"],
        nodes=r["nodes"],
        connections=r["connections"],
        settings=r.get("settings") or {},
        pin_data=r.get("pin_data"),
        graph_hash=r["graph_hash"],
        engine_version=r.get("engine_version") or 1,
        created_at=r["created_at"].replace(tzinfo=UTC),
        created_by=r["created_by"],
    )
    return {"flow": FlowHeader(flow_id=flow_id, **hdr), "revision": rev}


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/activate")
async def activate_flow(organization_id: str, flow_id: str, req: ActivateFlowRequest = Body(default={}), current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")
    target = req.flow_revid
    if not target:
        latest = await db.flow_revisions.find_one({"flow_id": flow_id}, sort=[("flow_version", -1)])
        if not latest:
            raise HTTPException(status_code=400, detail="Flow has no revisions")
        target = str(latest["_id"])
    r = await db.flow_revisions.find_one({"_id": ObjectId(target), "flow_id": flow_id})
    if not r:
        raise HTTPException(status_code=404, detail="Revision not found")

    nodes_raw = r.get("nodes") or []
    nodes_list = nodes_raw if isinstance(nodes_raw, list) else []
    try:
        rev_conns = ad.flows.coerce_json_connections_to_dataclasses(r.get("connections"))
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid connections: {e}") from e
    try:
        ad.flows.validate_revision(
            nodes_list,
            rev_conns,
            r.get("settings") or {},
            r.get("pin_data"),
        )
    except ad.flows.FlowValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if h.get("callable_as_tool"):
        from analytiq_data.flows.callable_flow import validate_callable_flow_revision

        try:
            validate_callable_flow_revision(nodes_list)
        except ad.flows.FlowValidationError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        await ad.flows.run_poll_activation_tests(
            ad.common.get_analytiq_client(),
            organization_id=organization_id,
            flow_id=flow_id,
            flow_revid=target,
            revision=r,
        )
    except ad.flows.FlowValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        await ad.docrouter_flows.event_dispatch.sync_docrouter_flow_triggers(
            db,
            org_id=organization_id,
            flow_id=flow_id,
            flow_revid=target,
            revision=r,
        )
    except ad.flows.FlowValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await db.flows.update_one(
        {"_id": ObjectId(flow_id)},
        {"$set": {"active": True, "active_flow_revid": target, "updated_at": _now(), "updated_by": current_user.user_id}},
    )
    trigger_svc = ad.flows.get_flow_trigger_service()
    if trigger_svc is not None:
        await trigger_svc.register_flow(
            organization_id, flow_id, target, r, run_immediately=True
        )
    return await get_flow(organization_id, flow_id, current_user)


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/deactivate")
async def deactivate_flow(organization_id: str, flow_id: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    res = await db.flows.update_one(
        {"_id": ObjectId(flow_id), "organization_id": organization_id},
        {"$set": {"active": False, "active_flow_revid": None, "updated_at": _now(), "updated_by": current_user.user_id}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Flow not found")
    await ad.docrouter_flows.event_dispatch.delete_docrouter_flow_triggers(db, flow_id=flow_id)
    trigger_svc = ad.flows.get_flow_trigger_service()
    if trigger_svc is not None:
        await trigger_svc.deregister_flow(flow_id)
    return await get_flow(organization_id, flow_id, current_user)


@flows_router.post(
    "/v0/orgs/{organization_id}/flows/{flow_id}/webhook-test/listen",
    response_model=ListenWebhookTestResponse,
)
async def listen_webhook_test(
    organization_id: str,
    flow_id: str,
    req: ListenWebhookTestRequest,
    current_user: User = Depends(get_org_user),
):
    """
    Store a short-lived draft snapshot for `/webhook-test/{leaf}`.

    This is what the editor uses for "Listen for test event": it should execute the current
    unsaved graph (`revision_snapshot`) rather than the activated production revision.
    """
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")

    leaf = (req.webhook_leaf or "").strip() or _extract_webhook_leaf_from_nodes(req.revision_snapshot.nodes) or str(uuid4())
    await _upsert_flow_webhook_route_leaf(db, leaf=leaf, flow_id=flow_id, organization_id=organization_id)
    await _clear_other_webhook_route_leaves_for_flow(db, flow_id=flow_id, keep_leaf=leaf)

    # Persist snapshot for test calls.
    await db.flow_webhook_routes.update_one(
        {"_id": leaf},
        {
            "$set": {
                "test.flow_id": flow_id,
                "test.organization_id": organization_id,
                "test.revision_snapshot": req.revision_snapshot.model_dump(),
                "test.expires_at": _now() + timedelta(hours=2),
                "updated_at": _now(),
            }
        },
        upsert=True,
    )
    return ListenWebhookTestResponse(
        webhook_leaf=leaf,
        test_path=f"/webhook-test/{leaf}",
        production_path=f"/webhook/{leaf}",
    )


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/webhook-test/stop")
async def stop_listen_webhook_test(
    organization_id: str,
    flow_id: str,
    req: StopWebhookTestRequest | None = Body(default=None),
    current_user: User = Depends(get_org_user),
):
    """
    Tear down editor test-mode listening so `/webhook-test/{leaf}` yields 404 again.

    Optionally pass `webhook_leaf` explicitly; otherwise the server tries to infer from the webhook node
    snapshot in ``req.revision_snapshot``.
    """

    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")

    leaf_any = ""
    if req:
        leaf_any = (req.webhook_leaf or "").strip() or ""
        snap = req.revision_snapshot
        if not leaf_any and snap and snap.nodes:
            leaf_any = (_extract_webhook_leaf_from_nodes(snap.nodes) or "").strip()

    leaf = leaf_any
    doc = await db.flow_webhook_routes.find_one({"_id": leaf}) if leaf else None

    # Best-effort: if caller didn't pass snapshot/leaf (or doc missing), locate any routes owned by this flow in test mode.
    if not doc:
        cand = await db.flow_webhook_routes.find_one({"test.flow_id": flow_id, "test.organization_id": organization_id})
        doc = cand
        leaf = str(doc["_id"]) if cand and cand.get("_id") else leaf

    if not doc:
        # Nothing to remove.
        return {"ok": True}

    test_any = doc.get("test") if isinstance(doc.get("test"), dict) else None
    if not test_any:
        return {"ok": True}
    if test_any.get("flow_id") != flow_id or test_any.get("organization_id") != organization_id:
        raise HTTPException(status_code=403, detail="Cannot stop webhook test listener for another flow")

    lid = doc.get("_id")
    await db.flow_webhook_routes.update_one(
        {"_id": lid},
        {"$unset": {"test": ""}, "$set": {"updated_at": _now()}},
    )
    leftover = await db.flow_webhook_routes.find_one({"_id": lid})
    if leftover and not isinstance(leftover.get("production"), dict) and not isinstance(leftover.get("test"), dict):
        await db.flow_webhook_routes.delete_one({"_id": lid})
    return {"ok": True}


@flows_router.post(
    "/v0/orgs/{organization_id}/flows/{flow_id}/trigger-test/schedule",
    response_model=ScheduleTriggerTestResponse,
)
async def trigger_test_schedule(
    organization_id: str,
    flow_id: str,
    req: ScheduleTriggerTestRequest,
    current_user: User = Depends(get_org_user),
):
    """
    Run the schedule trigger once against the editor snapshot (no activation required).

    Enqueues a ``flow_run`` with ``revision_snapshot`` so unsaved graph changes are included.
    """
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")

    snap = req.revision_snapshot
    nodes = snap.nodes
    try:
        conns_dc = ad.flows.coerce_json_connections_to_dataclasses(snap.connections)
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid connections: {e}") from e
    settings = snap.settings or {}
    pin_data = snap.pin_data
    try:
        ad.flows.validate_revision(nodes, conns_dc, settings, pin_data)
    except ad.flows.FlowValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    schedule_nodes = [
        n for n in nodes if isinstance(n, dict) and n.get("type") == "flows.trigger.schedule"
    ]
    if not schedule_nodes:
        raise HTTPException(status_code=400, detail="Flow has no schedule trigger")

    trigger_node_id = (req.trigger_node_id or "").strip()
    if not trigger_node_id:
        if len(schedule_nodes) != 1:
            raise HTTPException(
                status_code=400,
                detail="Multiple schedule triggers; pass trigger_node_id",
            )
        trigger_node_id = str(schedule_nodes[0]["id"])

    flow_revid_lineage = await _resolve_flow_revid_lineage(flow_id, None, db)
    revision_snapshot = {
        "nodes": nodes,
        "connections": snap.connections,
        "settings": settings,
        "pin_data": pin_data,
    }

    try:
        exec_id = await ad.flows.enqueue_schedule_trigger_test_run(
            ad.common.get_analytiq_client(),
            organization_id=organization_id,
            flow_id=flow_id,
            flow_revid_lineage=flow_revid_lineage,
            revision_snapshot=revision_snapshot,
            trigger_node_id=trigger_node_id,
        )
    except ad.flows.FlowValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return ScheduleTriggerTestResponse(execution_id=exec_id)


@flows_router.post(
    "/v0/orgs/{organization_id}/flows/{flow_id}/trigger-test/poll",
    response_model=ScheduleTriggerTestResponse,
)
async def trigger_test_poll(
    organization_id: str,
    flow_id: str,
    req: PollTriggerTestRequest,
    current_user: User = Depends(get_org_user),
):
    """
    Run a poll trigger once against the editor snapshot (no activation required).

    Enqueues a ``flow_run`` with ``revision_snapshot`` so unsaved graph changes are included.
    """
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")

    snap = req.revision_snapshot
    nodes = snap.nodes
    try:
        conns_dc = ad.flows.coerce_json_connections_to_dataclasses(snap.connections)
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid connections: {e}") from e
    settings = snap.settings or {}
    pin_data = snap.pin_data
    try:
        ad.flows.validate_revision(nodes, conns_dc, settings, pin_data)
    except ad.flows.FlowValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    poll_nodes: list[dict] = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        ntype = n.get("type") or ""
        try:
            nt = ad.flows.get(ntype)
        except KeyError:
            continue
        if getattr(nt, "polling", False):
            poll_nodes.append(n)
    if not poll_nodes:
        raise HTTPException(status_code=400, detail="Flow has no poll trigger")

    trigger_node_id = (req.trigger_node_id or "").strip()
    if not trigger_node_id:
        if len(poll_nodes) != 1:
            raise HTTPException(
                status_code=400,
                detail="Multiple poll triggers; pass trigger_node_id",
            )
        trigger_node_id = str(poll_nodes[0]["id"])

    flow_revid_lineage = await _resolve_flow_revid_lineage(flow_id, None, db)
    revision_snapshot = {
        "nodes": nodes,
        "connections": snap.connections,
        "settings": settings,
        "pin_data": pin_data,
    }

    try:
        exec_id = await ad.flows.enqueue_poll_trigger_test_run(
            ad.common.get_analytiq_client(),
            organization_id=organization_id,
            flow_id=flow_id,
            flow_revid_lineage=flow_revid_lineage,
            revision_snapshot=revision_snapshot,
            trigger_node_id=trigger_node_id,
        )
    except ad.flows.FlowValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return ScheduleTriggerTestResponse(execution_id=exec_id)


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/run")
async def run_flow(organization_id: str, flow_id: str, req: RunFlowRequest, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    h = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": organization_id})
    if not h:
        raise HTTPException(status_code=404, detail="Flow not found")

    rev: dict[str, Any] | None = None
    revision_snapshot: dict[str, Any] | None = None
    flow_revid_linage: str = ""

    if req.revision_snapshot is not None:
        snap = req.revision_snapshot
        nodes = snap.nodes
        try:
            conns_dc = ad.flows.coerce_json_connections_to_dataclasses(snap.connections)
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid connections: {e}") from e
        settings = snap.settings or {}
        pin_data = snap.pin_data
        try:
            ad.flows.validate_revision(nodes, conns_dc, settings, pin_data)
        except ad.flows.FlowValidationError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        revision_snapshot = {
            "nodes": nodes,
            "connections": snap.connections,
            "settings": settings,
            "pin_data": pin_data,
        }
        flow_revid_linage = await _resolve_flow_revid_lineage(flow_id, req.flow_revid, db)
    else:
        flow_revid = (req.flow_revid or "").strip()
        if not flow_revid:
            latest = await db.flow_revisions.find_one({"flow_id": flow_id}, sort=[("flow_version", -1)])
            if not latest:
                raise HTTPException(status_code=400, detail="Flow has no revisions")
            flow_revid = str(latest["_id"])

        rev = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid), "flow_id": flow_id})
        if not rev:
            raise HTTPException(status_code=404, detail="Revision not found")
        flow_revid_linage = flow_revid

    known_nodes = (revision_snapshot or rev or {}).get("nodes") or []
    known_node_ids = {str(n["id"]) for n in known_nodes if n.get("id")}
    if req.target_node_id and req.target_node_id not in known_node_ids:
        raise HTTPException(status_code=400, detail="target_node_id is not a node on the selected revision")

    if req.run_data and not req.target_node_id:
        raise HTTPException(status_code=400, detail="target_node_id is required when run_data is supplied")

    if req.tool_test_request is not None:
        if not req.target_node_id:
            raise HTTPException(status_code=400, detail="target_node_id is required with tool_test_request")
        target_node = next((n for n in known_nodes if n.get("id") == req.target_node_id), None)
        if not target_node:
            raise HTTPException(status_code=400, detail="target_node_id is not a node on the selected revision")
        try:
            target_type = ad.flows.get(str(target_node.get("type") or ""))
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Unknown node type on target: {target_node.get('type')}") from e
        if not getattr(target_type, "tool_provider", False):
            raise HTTPException(status_code=400, detail="tool_test_request requires a tool_provider target_node_id")
        snap_nodes = (revision_snapshot or rev or {}).get("nodes") or known_nodes
        snap_conns = (revision_snapshot or rev or {}).get("connections") or {}
        try:
            ad.flows.prepare_tool_test_run(
                revision={"nodes": snap_nodes, "connections": snap_conns, "settings": {}, "pin_data": None},
                tool_node_id=req.target_node_id,
                tool_name=req.tool_test_request.tool_name.strip(),
                arguments=dict(req.tool_test_request.arguments or {}),
            )
        except ad.flows.FlowValidationError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        seed_filtered = ad.flows.validate_and_filter_run_data_seed(
            known_node_ids=known_node_ids,
            seed=req.run_data,
        )
    except ad.flows.RunDataSeedValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    dirty_clean = ad.flows.finalized_dirty_node_ids(
        dirty_node_ids=req.dirty_node_ids,
        target_node_id=req.target_node_id,
        known_node_ids=known_node_ids,
    )

    exec_doc = {
        "flow_id": flow_id,
        "flow_revid": flow_revid_linage,
        "organization_id": organization_id,
        "mode": "manual",
        "status": "queued",
        "started_at": _now(),
        "finished_at": None,
        "last_heartbeat_at": None,
        "stop_requested": False,
        "last_node_executed": None,
        "wait_till": None,
        "retry_of": None,
        "parent_execution_id": None,
        "run_data": {},
        "error": None,
        "trigger": {"type": "manual"},
        "start_trigger_node_id": (req.start_trigger_node_id or "").strip() or None,
        "target_node_id": req.target_node_id,
        "initial_run_data": seed_filtered or None,
        "dirty_node_ids": dirty_clean or None,
        "completed_nodes": [],
        "resumed_from": None,
        "resumed_by": None,
    }
    if req.tool_test_request is not None:
        exec_doc["tool_test_request"] = {
            "tool_name": req.tool_test_request.tool_name.strip(),
            "arguments": dict(req.tool_test_request.arguments or {}),
        }
    if revision_snapshot is not None:
        exec_doc["revision_snapshot"] = revision_snapshot
    res_ins = await db.flow_executions.insert_one(exec_doc)
    exec_id = str(res_ins.inserted_id)

    await ad.queue.send_msg(ad.common.get_analytiq_client(), "flow_run", msg={
        "flow_id": flow_id,
        "flow_revid": flow_revid_linage or "",
        "execution_id": exec_id,
        "organization_id": organization_id,
        "trigger": exec_doc["trigger"],
    })
    return {"execution_id": exec_id}


@flows_router.get("/v0/orgs/{organization_id}/executions", response_model=ListExecutionsResponse)
async def list_executions(
    organization_id: str,
    flow_id: str | None = Query(None, description="When set, only executions for this flow"),
    status: str | None = Query(None, description="Filter by execution status"),
    mode: str | None = Query(None, description="Filter by execution mode"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_org_user),
):
    """List flow executions for the organization; optionally narrow by flow and filters."""

    _ = current_user
    db = await _get_db()
    query: dict[str, Any] = {"organization_id": organization_id}
    if flow_id:
        query["flow_id"] = flow_id
    if status:
        query["status"] = status
    if mode:
        query["mode"] = mode
    total = await db.flow_executions.count_documents(query)
    pipeline: list[dict[str, Any]] = [
        {"$match": query},
        {"$sort": {"started_at": -1}},
        {"$skip": offset},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "flows",
                "let": {"fid": "$flow_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": [{"$toString": "$_id"}, "$$fid"]}}},
                    {"$limit": 1},
                    {"$project": {"_id": 0, "name": 1}},
                ],
                "as": "_flow_join",
            }
        },
        {
            "$set": {
                "flow_name": {
                    "$let": {
                        "vars": {"fn": {"$arrayElemAt": ["$_flow_join.name", 0]}},
                        "in": "$$fn",
                    }
                }
            }
        },
        {"$project": {"_flow_join": 0}},
    ]
    docs = await db.flow_executions.aggregate(pipeline).to_list(limit)
    items = [_execution_doc_to_list_item(d) for d in docs]
    return {"items": items, "total": total}


@flows_router.get("/v0/orgs/{organization_id}/flows/{flow_id}/executions/{exec_id}", response_model=FlowExecution)
async def get_execution(organization_id: str, flow_id: str, exec_id: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    d = await db.flow_executions.find_one({"_id": ObjectId(exec_id), "flow_id": flow_id, "organization_id": organization_id})
    if not d:
        raise HTTPException(status_code=404, detail="Execution not found")
    return FlowExecution(
        execution_id=str(d["_id"]),
        flow_id=d["flow_id"],
        flow_revid=d["flow_revid"],
        organization_id=d["organization_id"],
        mode=d["mode"],
        status=d["status"],
        started_at=d["started_at"].replace(tzinfo=UTC) if isinstance(d.get("started_at"), datetime) else None,
        finished_at=d["finished_at"].replace(tzinfo=UTC) if isinstance(d.get("finished_at"), datetime) else d.get("finished_at"),
        last_heartbeat_at=d["last_heartbeat_at"].replace(tzinfo=UTC)
        if isinstance(d.get("last_heartbeat_at"), datetime)
        else d.get("last_heartbeat_at"),
        stop_requested=bool(d.get("stop_requested")),
        last_node_executed=d.get("last_node_executed"),
        run_data=d.get("run_data") or {},
        error=d.get("error"),
        trigger=d.get("trigger") or {},
        target_node_id=d.get("target_node_id"),
        initial_run_data=d.get("initial_run_data"),
    )


@flows_router.get("/v0/orgs/{organization_id}/flows/{flow_id}/executions/{exec_id}/blob")
async def get_execution_blob(
    organization_id: str,
    flow_id: str,
    exec_id: str,
    storage_id: str = Query(
        ...,
        min_length=1,
        description=(
            "BinaryRef.storage_id (bucket:key). Supports flow_blobs:, flow_pins:, and files: "
            "(permanent document GridFS keys; org ownership verified)."
        ),
    ),
    action: Literal["view", "download"] = Query(
        "download",
        description=(
            "`view`: inline preview only for image/* (excluding SVG) and PDF; other types use attachment. "
            "`download`: attachment."
        ),
    ),
    current_user: User = Depends(get_org_user),
):
    """Return bytes for a binary referenced in this execution's run data."""

    _ = current_user
    try:
        oid = ObjectId(exec_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Execution not found")

    db = await _get_db()
    exec_doc = await db.flow_executions.find_one(
        {"_id": oid, "flow_id": flow_id, "organization_id": organization_id}
    )
    if not exec_doc:
        raise HTTPException(status_code=404, detail="Execution not found")

    bucket, key = _parse_binary_storage_id(storage_id)
    aq_client = ad.common.get_analytiq_client()

    if bucket == "flow_blobs":
        if not key.startswith(f"{exec_id}/"):
            raise HTTPException(status_code=403, detail="Blob key does not belong to this execution")
        result = await ad.mongodb.blob.get_blob_async(aq_client, bucket="flow_blobs", key=key)
        blob = _gridfs_blob_bytes(result)
        mime, fname = _gridfs_meta_mime_and_filename(result.get("metadata"))
        return _binary_blob_http_response(blob=blob, mime=mime, file_name=fname, action=action)

    if bucket == "flow_pins":
        flow_revid = exec_doc.get("flow_revid")
        if not isinstance(flow_revid, str) or not flow_revid.strip():
            raise HTTPException(status_code=404, detail="Execution not found")
        await _require_flow_pins_key_for_revision(db, flow_id=flow_id, flow_revid=flow_revid, key=key)
        result = await ad.mongodb.blob.get_blob_async(aq_client, bucket="flow_pins", key=key)
        blob = _gridfs_blob_bytes(result)
        mime, fname = _gridfs_meta_mime_and_filename(result.get("metadata"))
        return _binary_blob_http_response(blob=blob, mime=mime, file_name=fname, action=action)

    if bucket == "files":
        blob, mime, fname = await _load_org_document_file_blob(
            db, aq_client, organization_id=organization_id, file_key=key
        )
        return _binary_blob_http_response(blob=blob, mime=mime, file_name=fname, action=action)

    raise HTTPException(status_code=400, detail="Invalid storage_id")


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/executions/{exec_id}/stop")
async def stop_execution(organization_id: str, flow_id: str, exec_id: str, current_user: User = Depends(get_org_user)):
    db = await _get_db()
    res = await db.flow_executions.update_one(
        {"_id": ObjectId(exec_id), "flow_id": flow_id, "organization_id": organization_id},
        {"$set": {"stop_requested": True}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {"ok": True}


@flows_router.post("/v0/orgs/{organization_id}/flows/{flow_id}/executions/{exec_id}/resume")
async def resume_execution(
    organization_id: str,
    flow_id: str,
    exec_id: str,
    current_user: User = Depends(get_org_user),
):
    """Enqueue a new run that continues from persisted node checkpoints."""
    _ = current_user
    try:
        exec_oid = ObjectId(exec_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Execution not found") from None

    db = await _get_db()
    doc = await db.flow_executions.find_one(
        {"_id": exec_oid, "flow_id": flow_id, "organization_id": organization_id},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Execution not found")

    status = doc.get("status")
    if status not in ad.flows.TERMINAL_RESUME_SOURCE_STATUSES:
        raise HTTPException(status_code=409, detail="Execution is not in a resumable terminal state")
    if doc.get("resumed_by"):
        raise HTTPException(status_code=409, detail="Execution was already resumed")
    if not doc.get("completed_nodes"):
        raise HTTPException(status_code=409, detail="Execution has no checkpoint nodes to resume from")

    client = ad.common.get_analytiq_client()
    new_id = await ad.flows.enqueue_resume_execution(client, db, doc)
    if not new_id:
        raise HTTPException(status_code=409, detail="Could not enqueue resume execution")
    return {"execution_id": new_id, "resumed_from": exec_id}


@flows_router.delete("/v0/orgs/{organization_id}/flows/{flow_id}/executions/{exec_id}")
async def delete_execution(organization_id: str, flow_id: str, exec_id: str, current_user: User = Depends(get_org_user)):
    """Delete a finished execution and its flow_blobs storage."""
    _ = current_user
    try:
        exec_oid = ObjectId(exec_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Execution not found") from None

    db = await _get_db()
    doc = await db.flow_executions.find_one(
        {"_id": exec_oid, "flow_id": flow_id, "organization_id": organization_id},
        {"status": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Execution not found")

    status = doc.get("status")
    if status in ("queued", "running"):
        raise HTTPException(status_code=409, detail="Stop the execution before deleting it")

    aq_client = ad.common.get_analytiq_client()
    await _delete_execution_blobs_and_doc(db, aq_client, exec_oid=exec_oid, exec_id=exec_id)
    return {"ok": True}


async def _inbound_webhook_common(
    *,
    db: Any,
    leaf: str,
    request: Request,
    mode: Literal["production", "test"],
) -> Response:
    """
    Shared inbound implementation for:
    - `/webhook/{leaf}` (production, activated revision)
    - `/webhook-test/{leaf}` (test, editor snapshot)
    """
    route = await db.flow_webhook_routes.find_one({"_id": leaf})
    if not route:
        raise HTTPException(status_code=404, detail="Unknown webhook")

    route_mode = route.get(mode) if isinstance(route.get(mode), dict) else None
    if not route_mode:
        raise HTTPException(status_code=404, detail="Unknown webhook")

    flow_id = route_mode.get("flow_id")
    org_id = route_mode.get("organization_id")
    if not flow_id or not org_id:
        raise HTTPException(status_code=404, detail="Unknown webhook")

    revision_doc: dict | None = None
    revision_snapshot: dict | None = None
    flow_revid_for_exec: str = ""

    if mode == "production":
        # Production: always run the activated saved revision.
        flow_doc = await db.flows.find_one({"_id": ObjectId(flow_id), "organization_id": org_id})
        if not flow_doc:
            raise HTTPException(status_code=404, detail="Flow not found")
        if not flow_doc.get("active") or not flow_doc.get("active_flow_revid"):
            raise HTTPException(status_code=409, detail="Flow is not active")
        flow_revid_for_exec = str(flow_doc["active_flow_revid"])
        try:
            revision_doc = await db.flow_revisions.find_one({"_id": ObjectId(flow_revid_for_exec), "flow_id": flow_id})
        except InvalidId:
            revision_doc = None
    else:
        # Test: run latest editor snapshot registered by /webhook-test/listen.
        expires_at = route_mode.get("expires_at")
        if isinstance(expires_at, datetime) and expires_at.replace(tzinfo=UTC) < _now():
            raise HTTPException(status_code=404, detail="Test webhook listener expired")
        snap_any = route_mode.get("revision_snapshot")
        revision_snapshot = dict(snap_any) if isinstance(snap_any, dict) else None

    params = ad.flows.webhook_params.extract_webhook_params_from_revision(
        revision_snapshot or revision_doc, webhook_leaf=leaf
    )
    webhook_trigger_node_id = ad.flows.webhook_params.resolve_webhook_trigger_node_id(
        revision_snapshot or revision_doc, leaf
    )
    response_mode = (params.get("response_mode") or "on_received").strip() if isinstance(params.get("response_mode"), str) else "on_received"

    allowed = ad.flows.webhook_params.allowed_http_methods_snapshot(params)
    if allowed is not None and request.method.upper() not in allowed:
        raise HTTPException(status_code=405, detail="Method not allowed")

    candidates = ad.flows.webhook_params.ip_whitelist_candidates(request)
    if not ad.flows.webhook_params.is_ip_whitelisted(params.get("ip_whitelist"), candidates):
        raise HTTPException(status_code=403, detail="IP is not whitelisted to access the webhook")

    if params.get("ignore_bots") and ad.flows.webhook_params.user_agent_looks_like_bot(
        request.headers.get("user-agent")
    ):
        raise HTTPException(status_code=403, detail="Bots are not allowed for this webhook")

    raw_body = bool(params.get("raw_body"))
    bpf = params.get("binary_property_name")
    binary_pn = bpf.strip() if isinstance(bpf, str) else "data"
    parsed = await ad.flows.webhook_parse.parse_webhook_request(
        request,
        raw_body=raw_body,
        binary_property_name=binary_pn,
    )

    trigger: dict[str, Any] = {
        "type": "webhook",
        "webhook_leaf": leaf,
        "webhook_mode": mode,
        "method": request.method,
        "headers": _sanitize_inbound_webhook_headers(request),
        "query": parsed.query or {},
        "body": parsed.body,
        "form": parsed.form,
        "binary_properties": [],
        # Used only when building webhook trigger ``FlowItem.json`` (`webhookUrl` field).
        "webhook_url": _inbound_webhook_canonical_public_url(request),
        # Raw body bytes live in binary output only (`FlowItem.binary`), not ``json.body``.
        "body_stashed_as_binary": bool(getattr(parsed, "body_stashed_as_binary", False)),
    }
    exec_doc = {
        "flow_id": flow_id,
        "flow_revid": flow_revid_for_exec,
        "organization_id": org_id,
        "mode": "webhook" if mode == "production" else "webhook_test",
        "status": "queued",
        "started_at": _now(),
        "finished_at": None,
        "last_heartbeat_at": None,
        "stop_requested": False,
        "last_node_executed": None,
        "wait_till": None,
        "retry_of": None,
        "parent_execution_id": None,
        "run_data": {},
        "error": None,
        "trigger": trigger,
        "start_trigger_node_id": webhook_trigger_node_id,
        "completed_nodes": [],
        "resumed_from": None,
        "resumed_by": None,
    }
    if revision_snapshot is not None:
        exec_doc["revision_snapshot"] = revision_snapshot
    res = await db.flow_executions.insert_one(exec_doc)
    exec_id = str(res.inserted_id)

    aq_client = ad.common.get_analytiq_client()
    trigger = await _webhook_finalize_pending_uploads(db, aq_client, exec_id, trigger, parsed.pending_binaries)

    # Synchronous response modes: execute in-process and return response payload.
    if response_mode in ("respond_to_webhook", "last_node"):
        flow_log_level = await ad.flows.fetch_org_flow_log_level(db, org_id)
        ctx = ad.flows.ExecutionContext(
            organization_id=org_id,
            execution_id=exec_id,
            flow_id=flow_id,
            flow_revid=flow_revid_for_exec,
            mode="webhook",
            trigger_data=trigger,
            run_data={},
            analytiq_client=aq_client,
            stop_requested=False,
            logger=None,
            flow_log_level=flow_log_level,
        )

        rev_for_run = revision_snapshot or revision_doc
        if not isinstance(rev_for_run, dict):
            raise HTTPException(status_code=500, detail="Missing flow revision for webhook execution")

        claim = await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id), "status": "queued"},
            {"$set": {"status": "running", "last_heartbeat_at": datetime.now(UTC)}},
        )
        if claim.matched_count == 0:
            raise HTTPException(status_code=409, detail="Execution is not in queued state for synchronous run")

        # Bound synchronous webhook execution time; keep a conservative default.
        # Mirror msg_handlers/flow_run.py: persist terminal status so worker_flow_cleanup can reap rows.
        try:
            result = await asyncio.wait_for(
                ad.flows.run_flow(
                    context=ctx,
                    revision=rev_for_run,
                    start_trigger_node_id=webhook_trigger_node_id,
                ),
                timeout=25.0,
            )
        except asyncio.TimeoutError:
            ts = datetime.now(UTC)
            err = ad.flows.execution_error_envelope(asyncio.TimeoutError("Execution timed out"))
            await db.flow_executions.update_one(
                {"_id": ObjectId(exec_id)},
                {
                    "$set": {
                        "status": "error",
                        "finished_at": ts,
                        "last_heartbeat_at": ts,
                        "error": err,
                    }
                },
            )
            raise HTTPException(status_code=500, detail="Webhook execution failed: Execution timed out") from None
        except Exception as e:
            ts = datetime.now(UTC)
            err = ad.flows.execution_error_envelope(e, run_data=ctx.run_data)
            patch: dict[str, Any] = {
                "status": "error",
                "finished_at": ts,
                "last_heartbeat_at": ts,
                "error": err,
            }
            node_id = err.get("node_id")
            if isinstance(node_id, str) and node_id.strip():
                patch["last_node_executed"] = node_id.strip()
            await db.flow_executions.update_one(
                {"_id": ObjectId(exec_id)},
                {"$set": patch},
            )
            raise HTTPException(status_code=500, detail=f"Webhook execution failed: {e}") from e

        terminal_status = result.get("status") or "success"
        ts = datetime.now(UTC)
        await db.flow_executions.update_one(
            {"_id": ObjectId(exec_id)},
            {"$set": {"status": terminal_status, "finished_at": ts, "last_heartbeat_at": ts}},
        )

        # Prefer explicit Respond to Webhook node payload.
        resp_any = ctx.trigger_data.get("_webhook_response")
        if response_mode == "respond_to_webhook" and isinstance(resp_any, dict):
            sc = resp_any.get("status_code")
            try:
                status = int(sc) if sc is not None else 200
            except (TypeError, ValueError):
                status = 200
            hdrs = resp_any.get("headers")
            headers = dict(hdrs) if isinstance(hdrs, dict) else {}
            if resp_any.get("body_is_none"):
                return Response(status_code=status, headers=headers)
            body_txt = resp_any.get("body_bytes_utf8")
            body_bytes = (body_txt if isinstance(body_txt, str) else "").encode("utf-8")
            return Response(content=body_bytes, status_code=status, headers=headers)

        if response_mode == "respond_to_webhook":
            # No responder node found; fall back to default ack.
            sync_status, hdr_map, payload = ad.flows.webhook_params.synchronous_http_response(exec_id, params)
            if payload is None:
                return Response(status_code=sync_status, headers=dict(hdr_map))
            return Response(content=payload, status_code=sync_status, headers=dict(hdr_map))

        # last_node: primary JSON from graph sink node(s); parallel branches tie-break by finish time.
        last_node_id = ad.flows.pick_webhook_last_node_id(
            ctx.run_data, rev_for_run, start_trigger_node_id=webhook_trigger_node_id
        )
        out_json: Any = {"execution_id": exec_id}
        if isinstance(last_node_id, str):
            ent = ctx.run_data.get(last_node_id) or {}
            try:
                main = ent.get("data", {}).get("main")  # type: ignore[union-attr]
                if isinstance(main, list) and main and isinstance(main[0], list) and main[0]:
                    it = main[0][0]
                    out_json = it.json if hasattr(it, "json") else out_json
            except Exception:
                pass
        body = json.dumps(out_json, default=str).encode("utf-8")
        return Response(content=body, status_code=200, headers={"Content-Type": "application/json"})

    await ad.queue.send_msg(
        aq_client,
        "flow_run",
        msg={
            "flow_id": flow_id,
            "flow_revid": flow_revid_for_exec,
            "execution_id": exec_id,
            "organization_id": org_id,
            "trigger": trigger,
        },
    )
    sync_status, hdr_map, payload = ad.flows.webhook_params.synchronous_http_response(exec_id, params)
    if payload is None:
        return Response(status_code=sync_status, headers=dict(hdr_map))
    return Response(content=payload, status_code=sync_status, headers=dict(hdr_map))


@flows_router.api_route("/webhook/{leaf}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def inbound_webhook_production(leaf: str, request: Request):
    db = await _get_db()
    return await _inbound_webhook_common(db=db, leaf=leaf, request=request, mode="production")

@flows_router.api_route(
    "/v0/orgs/{organization_id}/flows/webhook/{leaf}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
)
async def inbound_webhook_production_scoped(organization_id: str, leaf: str, request: Request):
    db = await _get_db()
    # The leaf is system-wide unique; org id here is for URL shape parity and logging.
    return await _inbound_webhook_common(db=db, leaf=leaf, request=request, mode="production")


@flows_router.api_route("/webhook-test/{leaf}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def inbound_webhook_test(leaf: str, request: Request):
    db = await _get_db()
    return await _inbound_webhook_common(db=db, leaf=leaf, request=request, mode="test")

@flows_router.api_route(
    "/v0/orgs/{organization_id}/flows/webhook-test/{leaf}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
)
async def inbound_webhook_test_scoped(organization_id: str, leaf: str, request: Request):
    db = await _get_db()
    return await _inbound_webhook_common(db=db, leaf=leaf, request=request, mode="test")


# Backward-compatible route (deprecated): `/v0/webhooks/{id}` used older webhook ids.
@flows_router.api_route("/v0/webhooks/{webhook_id}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def inbound_webhook(webhook_id: str, request: Request):
    db = await _get_db()
    return await _inbound_webhook_common(db=db, leaf=webhook_id, request=request, mode="production")

