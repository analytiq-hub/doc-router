from __future__ import annotations

"""
Core flow engine implementation.

This module is the DocRouter-independent execution and validation layer for flow
revisions as specified in `docs/flows.md`.
"""

import asyncio
import collections
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import AbstractSet, Any

from bson import ObjectId
from jsonschema import Draft7Validator

import analytiq_data as ad

from .errors import FlowValidationError, node_error_envelope
from .node_name import node_name
from .flow_settings import validate_flow_settings
from .node_settings import validate_node_batch_size
from .port_types import FLOWS_TOOL_CONNECTION_TYPE, input_port_types_for, output_port_types_for
from .trace import pop_node_trace
from .triggers.cron_exprs import poll_times_to_specs
from .triggers.poll_defaults import resolve_poll_times


logger = logging.getLogger(__name__)


_CANONICAL_NODE_REF_PREFIX = "#id:"


def _rewrite_node_primary_refs_in_expression(expr_body: str, old_display: str, new_display: str) -> str:
    if old_display == new_display:
        return expr_body
    escaped = re.escape(old_display)
    new_key = f"_node[{json.dumps(new_display)}]"
    pat = re.compile(rf"_node\[(['\"]){escaped}\1\]")
    return pat.sub(new_key, expr_body)


def _normalize_expr_node_refs_to_ids(expr_body: str, nodes: list[dict[str, Any]]) -> str:
    out = expr_body
    for n in nodes:
        nid = n.get("id")
        if not isinstance(nid, str) or not nid:
            continue
        display = node_name(n)
        canonical = f"{_CANONICAL_NODE_REF_PREFIX}{nid}"
        out = _rewrite_node_primary_refs_in_expression(out, display, canonical)
    return out


def _normalize_value_for_graph_hash(value: Any, nodes: list[dict[str, Any]]) -> Any:
    if isinstance(value, str):
        stripped = value.lstrip()
        if not stripped.startswith("="):
            return value
        lead_len = len(value) - len(stripped)
        lead = value[:lead_len]
        body = stripped[1:]
        return f"{lead}={_normalize_expr_node_refs_to_ids(body, nodes)}"
    if isinstance(value, list):
        return [_normalize_value_for_graph_hash(v, nodes) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_value_for_graph_hash(v, nodes) for k, v in value.items()}
    return value


def _nodes_for_graph_hash(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip canvas-only node fields before hashing (layout/labels must not bump flow version)."""
    out: list[dict[str, Any]] = []
    for n in nodes:
        stripped = {k: v for k, v in n.items() if k not in ("position", "name")}
        params = stripped.get("parameters")
        if params is not None:
            stripped = {**stripped, "parameters": _normalize_value_for_graph_hash(params, nodes)}
        out.append(stripped)
    return out


def canonical_graph_hash(
    nodes: list[dict[str, Any]], connections: "ad.flows.Connections", settings: dict[str, Any]
) -> str:
    """Return a stable SHA-256 hash of the flow graph for dedup/version checks."""

    payload = {
        "nodes": _nodes_for_graph_hash(nodes),
        "connections": connections,
        "settings": settings,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _toposort(nodes: list[dict[str, Any]], connections: "ad.flows.Connections") -> list[str]:
    """Topologically sort node ids or raise `FlowValidationError` if a cycle exists."""

    node_ids = {n["id"] for n in nodes}
    indeg: dict[str, int] = {nid: 0 for nid in node_ids}
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}

    for src, typed in (connections or {}).items():
        if src not in node_ids:
            continue
        main_slots = (typed or {}).get("main") or []
        for slot in main_slots:
            if not slot:
                continue
            for conn in slot:
                if conn.dest_node_id in node_ids and conn.connection_type != FLOWS_TOOL_CONNECTION_TYPE:
                    adj[src].append(conn.dest_node_id)
                    indeg[conn.dest_node_id] += 1

    q: collections.deque[str] = collections.deque(nid for nid, d in indeg.items() if d == 0)
    out: list[str] = []
    while q:
        nid = q.popleft()
        out.append(nid)
        for dst in adj[nid]:
            indeg[dst] -= 1
            if indeg[dst] == 0:
                q.append(dst)

    if len(out) != len(node_ids):
        raise FlowValidationError("Graph contains a cycle (DAG required)")
    return out


def validate_revision(
    nodes: list[dict[str, Any]],
    connections: "ad.flows.Connections",
    settings: dict[str, Any] | None,
    pin_data: dict[str, Any] | None,
) -> None:
    """
    Validate a flow revision against v1 rules.

    At least one trigger node is required (including for an otherwise empty graph). Then enforces
    uniqueness (ids/names), reachability from a trigger, DAG, connection bounds, and structural
    credential checks.
    """

    settings = settings or {}
    ad.flows.ensure_builtin_keys_for_revision(nodes=nodes)

    if not nodes:
        if connections:
            raise FlowValidationError("Cannot save connections when the flow has no nodes")
        if pin_data:
            raise FlowValidationError("Cannot save pin_data when the flow has no nodes")
        raise FlowValidationError("Flow must contain at least one trigger node")

    node_ids = [n.get("id") for n in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise FlowValidationError("nodes[].id must be unique")

    node_names = [n.get("name") for n in nodes]
    if len(node_names) != len(set(node_names)):
        raise FlowValidationError("nodes[].name must be unique")

    nodes_by_id = {n["id"]: n for n in nodes}

    trigger_nodes: list[dict[str, Any]] = []
    for n in nodes:
        try:
            nt = ad.flows.get(n["type"])
        except KeyError:
            raise FlowValidationError(f"Unknown node type: {n['type']}") from None
        if nt.is_trigger:
            trigger_nodes.append(n)

    if len(trigger_nodes) < 1:
        raise FlowValidationError("Flow must contain at least one trigger node")

    # Reachability: every node must lie on a path from at least one trigger (union of subgraphs).
    reachable: set[str] = set()
    frontier = [t["id"] for t in trigger_nodes]
    for tid in frontier:
        reachable.add(tid)
    while frontier:
        cur = frontier.pop()
        typed = (connections or {}).get(cur) or {}
        main_slots = typed.get("main") or []
        for slot in main_slots:
            if not slot:
                continue
            for conn in slot:
                if conn.dest_node_id not in reachable:
                    reachable.add(conn.dest_node_id)
                    frontier.append(conn.dest_node_id)
    for n in nodes:
        try:
            nt = ad.flows.get(n["type"])
        except KeyError:
            raise FlowValidationError(f"Unknown node type: {n['type']}") from None
        if getattr(nt, "tool_provider", False):
            continue
        if n["id"] not in reachable:
            raise FlowValidationError(f"Node {ad.flows.node_name(n)} is not reachable from any trigger")

    from analytiq_data.flows.tool_wiring import validate_tool_graph

    validate_tool_graph(nodes, connections or {})

    # Connection validation.
    for src, typed in (connections or {}).items():
        if src not in nodes_by_id:
            raise FlowValidationError(f"Connection source node id does not exist: {src}")
        try:
            src_type = ad.flows.get(nodes_by_id[src]["type"])
        except KeyError:
            raise FlowValidationError(f"Unknown node type: {nodes_by_id[src]['type']}") from None
        main_slots = (typed or {}).get("main") or []
        for out_idx, slot in enumerate(main_slots):
            if out_idx >= src_type.outputs:
                raise FlowValidationError(
                    f"Source node {ad.flows.node_name(nodes_by_id[src])} output index out of range: {out_idx}"
                )
            if not slot:
                continue
            for conn in slot:
                if conn.connection_type == FLOWS_TOOL_CONNECTION_TYPE:
                    if conn.dest_node_id not in nodes_by_id:
                        raise FlowValidationError(
                            f"Connection destination node id does not exist: {conn.dest_node_id}"
                        )
                    dst_node = nodes_by_id[conn.dest_node_id]
                    try:
                        dst_type = ad.flows.get(dst_node["type"])
                        src_type_tool = ad.flows.get(nodes_by_id[src]["type"])
                    except KeyError:
                        raise FlowValidationError(f"Unknown node type on tool connection") from None
                    if not getattr(src_type_tool, "tool_provider", False):
                        raise FlowValidationError(
                            f"Node {ad.flows.node_name(nodes_by_id[src])} cannot emit flows.tool connections"
                        )
                    if not getattr(dst_type, "tool_consumer", False):
                        raise FlowValidationError(
                            f"Node {ad.flows.node_name(dst_node)} does not accept flows.tool connections"
                        )
                    if conn.index < 0:
                        raise FlowValidationError("Tool connection index must be >= 0")
                    src_out_types = output_port_types_for(src_type_tool)
                    expected_type = src_out_types[out_idx] if out_idx < len(src_out_types) else "main"
                    if expected_type != FLOWS_TOOL_CONNECTION_TYPE:
                        raise FlowValidationError(
                            f"Tool connection from {ad.flows.node_name(nodes_by_id[src])} "
                            f"output {out_idx} must use connection_type {FLOWS_TOOL_CONNECTION_TYPE!r}"
                        )
                    continue

                if conn.dest_node_id not in nodes_by_id:
                    raise FlowValidationError(
                        f"Connection destination node id does not exist: {conn.dest_node_id}"
                    )
                try:
                    dst_type = ad.flows.get(nodes_by_id[conn.dest_node_id]["type"])
                except KeyError:
                    raise FlowValidationError(f"Unknown node type: {nodes_by_id[conn.dest_node_id]['type']}") from None
                if conn.index < 0:
                    raise FlowValidationError("Connection destination index must be >= 0")
                if dst_type.max_inputs is not None and conn.index >= dst_type.max_inputs:
                    raise FlowValidationError(
                        f"Connection destination index out of range for node "
                        f"{ad.flows.node_name(nodes_by_id[conn.dest_node_id])}: {conn.index}"
                    )
                if conn.index >= max(dst_type.min_inputs, (dst_type.max_inputs or conn.index + 1)):
                    # Best-effort; for unbounded max_inputs we accept any index >= 0.
                    if dst_type.max_inputs is not None:
                        raise FlowValidationError(
                            f"Connection destination index out of range for node "
                            f"{ad.flows.node_name(nodes_by_id[conn.dest_node_id])}: {conn.index}"
                        )
                src_out_types = output_port_types_for(src_type)
                dst_in_types = input_port_types_for(dst_type)
                expected_type = src_out_types[out_idx] if out_idx < len(src_out_types) else "main"
                if conn.connection_type != expected_type:
                    raise FlowValidationError(
                        f"Connection from {ad.flows.node_name(nodes_by_id[src])} output {out_idx} "
                        f"must use connection_type {expected_type!r}, got {conn.connection_type!r}"
                    )
                if conn.index >= len(dst_in_types):
                    raise FlowValidationError(
                        f"Connection destination index out of range for node "
                        f"{ad.flows.node_name(nodes_by_id[conn.dest_node_id])}: {conn.index}"
                    )
                accepted_type = dst_in_types[conn.index]
                if conn.connection_type != accepted_type:
                    raise FlowValidationError(
                        f"Connection to {ad.flows.node_name(nodes_by_id[conn.dest_node_id])} "
                        f"input {conn.index} requires connection_type {accepted_type!r}, "
                        f"got {conn.connection_type!r}"
                    )

    # Acyclic.
    _toposort(nodes, connections or {})

    # Parameter schema validation is deferred to execution time (after expression
    # resolution), so that expression-valued fields are not rejected by Draft7Validator.
    # Only node-type-level structural checks run here.
    for n in nodes:
        try:
            nt = ad.flows.get(n["type"])
        except KeyError:
            raise FlowValidationError(f"Unknown node type: {n['type']}") from None

        creds = n.get("credentials")
        if creds is not None:
            if not isinstance(creds, dict):
                raise FlowValidationError(f"Node {ad.flows.node_name(n)} credentials must be an object")
            slots_raw = getattr(nt, "credential_slots", None) or []
            allowed = {
                str(s["slot"])
                for s in slots_raw
                if isinstance(s, dict) and s.get("slot") is not None
            }
            for slot_name, cred_id in creds.items():
                if slot_name not in allowed:
                    raise FlowValidationError(
                        f"Unknown credential slot {slot_name!r} for node {ad.flows.node_name(n)} ({nt.key})"
                    )
                if cred_id is None or cred_id == "":
                    continue
                if not isinstance(cred_id, str):
                    raise FlowValidationError(
                        f"Credential binding for slot {slot_name!r} on node {ad.flows.node_name(n)} must be a string id"
                    )

        if nt.key == "flows.trigger.schedule":
            param_errs = nt.validate_parameters(n.get("parameters") or {})
            if param_errs:
                raise FlowValidationError(
                    f"Node {ad.flows.node_name(n)}: {'; '.join(param_errs)}"
                )
        elif getattr(nt, "polling", False):
            param_errs = nt.validate_parameters(n.get("parameters") or {})
            if param_errs:
                raise FlowValidationError(
                    f"Node {ad.flows.node_name(n)}: {'; '.join(param_errs)}"
                )
            try:
                poll_times_to_specs(resolve_poll_times(n.get("parameters") or {}))
            except Exception as e:
                raise FlowValidationError(
                    f"Node {ad.flows.node_name(n)}: {e}"
                ) from e

        for msg in validate_node_batch_size(n):
            raise FlowValidationError(f"Node {ad.flows.node_name(n)}: {msg}")

    for msg in validate_flow_settings(settings):
        raise FlowValidationError(msg)

    if pin_data:
        for node_id in pin_data.keys():
            if node_id not in nodes_by_id:
                raise FlowValidationError(f"pin_data references unknown node id: {node_id}")


def _validate_resolved_params(resolved_node: dict[str, Any]) -> None:
    """
    Validate resolved (expression-free) parameters against the node's JSON Schema
    and node-type-specific rules. Called after `resolve_parameters()`.
    """
    resolved = resolved_node.get("parameters") or {}
    nt = ad.flows.get(resolved_node["type"])
    label = ad.flows.node_name(resolved_node)
    try:
        Draft7Validator(nt.parameter_schema).validate(resolved)
    except Exception as e:
        raise RuntimeError(
            f"Parameter validation failed for node {label} ({nt.key}): {e}"
        ) from e
    errs = nt.validate_parameters(resolved) or []
    if errs:
        raise RuntimeError(
            f"Parameter validation failed for node {label} ({nt.key}): {'; '.join(errs)}"
        )


def _empty_outputs(outputs: int) -> list[list["ad.flows.FlowItem"]]:
    """Return `outputs` empty output-slot lists (branch-skipping / disabled behavior)."""

    return [[] for _ in range(outputs)]


def _error_item(node_id: str, node_name: str, message: str) -> "ad.flows.FlowItem":
    """Create a single-item error envelope suitable for `on_error="continue"`."""

    return ad.flows.FlowItem(
        json={"_error": {"node_id": node_id, "node_name": node_name, "message": message}},
        binary={},
        meta={},
        paired_item=None,
    )


@dataclass
class _WorkItem:
    """Internal queue item pairing a node id with its input slots."""

    node_id: str
    inputs: list[list["ad.flows.FlowItem"]]
    #: Per input slot: upstream provenance (``run_data[node_id].source``).
    source: list[list[dict[str, Any]]] | None = None


def _source_ref(
    previous_node_id: str,
    *,
    previous_node_output: int = 0,
    previous_node_run: int = 0,
) -> dict[str, Any]:
    return {
        "previous_node_id": previous_node_id,
        "previous_node_output": previous_node_output,
        "previous_node_run": previous_node_run,
    }


def _work_item_source_record(wi: _WorkItem) -> list[list[dict[str, Any]]]:
    if wi.source is not None:
        return wi.source
    return [[] for _ in range(len(wi.inputs))]


def _with_output_paired_item(
    out: "ad.flows.FlowItem",
    *,
    input_slot: int,
    input_item_index: int,
) -> "ad.flows.FlowItem":
    meta = dict(out.meta) if isinstance(out.meta, dict) else {}
    meta.setdefault("item_index", input_item_index)
    meta.setdefault("input_slot", input_slot)
    paired = out.paired_item if out.paired_item is not None else input_item_index
    return ad.flows.FlowItem(
        json=out.json,
        binary=out.binary,
        meta=meta,
        paired_item=paired,
    )


def _stamp_outputs_producer_meta(
    out_lists: list[list["ad.flows.FlowItem"]],
    *,
    producer_node_id: str,
) -> list[list["ad.flows.FlowItem"]]:
    """Set ``meta.source_node_id`` on every output item to the node that produced it."""

    stamped: list[list["ad.flows.FlowItem"]] = []
    for slot in out_lists:
        slot_out: list["ad.flows.FlowItem"] = []
        for item_idx, it in enumerate(slot):
            meta = dict(it.meta) if isinstance(it.meta, dict) else {}
            meta["source_node_id"] = producer_node_id
            meta.setdefault("item_index", item_idx)
            slot_out.append(
                ad.flows.FlowItem(
                    json=it.json,
                    binary=it.binary,
                    meta=meta,
                    paired_item=it.paired_item,
                )
            )
        stamped.append(slot_out)
    return stamped


async def save_execution_binary_blob(
    analytiq_client: Any,
    *,
    execution_id: str,
    node_id: str,
    item_index: int,
    property_name: str,
    blob: bytes,
    mime_type: str,
    file_name: str | None = None,
) -> "ad.flows.BinaryRef":
    """
    Upload bytes to GridFS ``flow_blobs`` for this execution and return a by-reference ``BinaryRef``.

    Key shape matches ``_offload_binary_refs`` so execution blob download and purge stay consistent.
    When ``analytiq_client`` is None (engine unit tests without Mongo), returns inline ``data`` instead.
    """

    fname = (file_name or "").strip() or property_name
    if analytiq_client is None:
        return ad.flows.BinaryRef(
            mime_type=mime_type,
            file_name=fname,
            data=blob,
            file_size=len(blob),
        )
    key = f"{execution_id}/{node_id}/{item_index}/{property_name}"
    await ad.mongodb.blob.save_blob_async(
        analytiq_client,
        bucket="flow_blobs",
        key=key,
        blob=blob,
        metadata={
            "mime_type": mime_type,
            "file_name": fname,
            "file_size": len(blob),
        },
    )
    return ad.flows.BinaryRef(
        mime_type=mime_type,
        file_name=fname,
        storage_id=f"flow_blobs:{key}",
        file_size=len(blob),
    )


def _bson_serialize_value(obj: Any) -> Any:
    """Recursively turn `FlowItem` / `BinaryRef` (and containers) into BSON-safe data."""

    if isinstance(obj, ad.flows.FlowItem):
        return {
            "json": obj.json,
            "binary": {k: _bson_serialize_value(v) for k, v in obj.binary.items()},
            "meta": obj.meta,
            "paired_item": obj.paired_item,
        }
    if isinstance(obj, ad.flows.BinaryRef):
        # Never persist inline bytes into MongoDB run_data (can exceed BSON limits).
        # Offload should have moved `data` to GridFS and set `storage_id` before serialization.
        if obj.data is not None and not obj.storage_id:
            raise RuntimeError(
                f"BinaryRef.data must be offloaded before persistence (file={obj.file_name!r})"
            )
        if not obj.storage_id:
            raise RuntimeError(
                f"BinaryRef.storage_id must be set before persistence (file={obj.file_name!r})"
            )
        out: dict[str, Any] = {
            "mime_type": obj.mime_type,
            "file_name": obj.file_name,
            "storage_id": obj.storage_id,
        }
        if obj.file_size is not None:
            out["file_size"] = obj.file_size
        return out
    if isinstance(obj, list):
        return [_bson_serialize_value(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _bson_serialize_value(v) for k, v in obj.items()}
    return obj


def _bson_serialize_run_data(run_data: dict[str, Any]) -> dict[str, Any]:
    return {k: _bson_serialize_value(v) for k, v in run_data.items()}


def pin_data_enabled_for_mode(mode: str) -> bool:
    """Pinned outputs are editor/test aids only (n8n parity); production runs ignore ``pin_data``."""

    return mode == "manual"


def apply_revision_pins_to_run_data(
    run_data: dict[str, Any],
    revision: dict[str, Any],
    *,
    allowed_node_ids: AbstractSet[str] | None = None,
) -> set[str]:
    """
    Inject or replace ``run_data[node_id]`` with a pinned output snapshot **before** the engine loop.

    Call only for ``manual`` executions (see ``pin_data_enabled_for_mode``).

    Execute-step merges prior ``initial_run_data`` into ``run_data``; without this, seeded merge
    (or branch) snapshots can contradict ``revision.pin_data``. Pinned lane-0 output wins for nodes
    in scope (execute-step subgraph when ``allowed_node_ids`` is set; for full runs with a chosen
    ``start_trigger_node_id``, forward reachability from that trigger; entire revision otherwise).

    Returns ids of nodes whose snapshots were overwritten from ``pin_data``.
    """

    touched: set[str] = set()
    pin_raw_all = revision.get("pin_data")
    if not pin_raw_all or not isinstance(pin_raw_all, dict):
        return touched
    nodes_by_id = {str(n["id"]): n for n in (revision.get("nodes") or []) if n.get("id") is not None}
    now = datetime.now(UTC)
    for node_id_any, pin_entry in pin_raw_all.items():
        nid = str(node_id_any)
        if nid not in nodes_by_id:
            continue
        if allowed_node_ids is not None and nid not in allowed_node_ids:
            continue
        node = nodes_by_id[nid]
        try:
            nt = ad.flows.get(node["type"])
        except Exception:
            continue
        outputs_count = int(nt.outputs)
        try:
            items = ad.flows.coerce_pin_data_node_output(pin_entry)
        except Exception:
            continue
        out_lists = [items] + [[] for _ in range(max(0, outputs_count - 1))]
        ser_main = [[_bson_serialize_value(x) for x in lane] for lane in out_lists]
        run_data[nid] = {
            "status": "success",
            "start_time": now.isoformat(),
            "execution_time_ms": 0,
            "data": {"main": ser_main},
            "error": None,
        }
        touched.add(nid)
    return touched


def invalidate_run_data_downstream_of_pins(
    run_data: dict[str, Any],
    connections: "ad.flows.Connections",
    pin_overlay_sources: AbstractSet[str],
    *,
    limit_nodes: AbstractSet[str] | None = None,
) -> None:
    """
    Drop seeded ``run_data`` for nodes downstream of pinned snapshots.

    When inputs change (pins), successors must not reuse stale ``initial_run_data`` entries — otherwise
    execute-step skips re-running the target while ``seed_entry_is_reusable`` returns true.

    Nodes in ``pin_overlay_sources`` keep their overlays; only strict descendants are purged.

    ``limit_nodes`` (execute-step subgraph) prevents touching ids outside the partial graph when provided.
    """

    if not pin_overlay_sources:
        return
    src_frozen = frozenset(str(x) for x in pin_overlay_sources)
    q: collections.deque[str] = collections.deque()
    seen_out: set[str] = set()
    for src in src_frozen:
        typed = (connections.get(src) or {})
        for slot in typed.get("main") or []:
            if not slot:
                continue
            for conn in slot:
                d = conn.dest_node_id
                if limit_nodes is not None and d not in limit_nodes:
                    continue
                if d in src_frozen or d in seen_out:
                    continue
                seen_out.add(d)
                q.append(d)
    while q:
        cur = q.popleft()
        if cur not in src_frozen:
            run_data.pop(cur, None)
        typed = (connections.get(cur) or {})
        for slot in typed.get("main") or []:
            if not slot:
                continue
            for conn in slot:
                d = conn.dest_node_id
                if limit_nodes is not None and d not in limit_nodes:
                    continue
                if d in seen_out:
                    continue
                seen_out.add(d)
                q.append(d)


def prune_run_data_outside_closure(
    run_data: dict[str, Any],
    allowed_node_ids: AbstractSet[str],
) -> None:
    """
    Remove per-node ``run_data`` entries that are outside ``allowed_node_ids``.

    Used when ``run_data`` is narrowed to a subgraph: execute-step (upstream closure), or a full run
    rooted at one trigger (forward-reachable node ids). Drops panel seed from unrelated parallel
    branches so they are not shown as having succeeded in this execution.
    """

    stale = [
        k
        for k in list(run_data.keys())
        if isinstance(k, str) and not k.startswith("_") and k not in allowed_node_ids
    ]
    for k in stale:
        del run_data[k]


def _upstream_nodes_reaching_target(
    target_id: str,
    connections: "ad.flows.Connections",
) -> set[str]:
    """All node ids that can reach ``target_id`` via a reverse walk along ``main`` edges."""

    rev: dict[str, list[str]] = {}
    for src, typed in (connections or {}).items():
        for slot in (typed or {}).get("main") or []:
            if not slot:
                continue
            for conn in slot:
                rev.setdefault(conn.dest_node_id, []).append(src)
    seen: set[str] = {target_id}
    stack = [target_id]
    while stack:
        cur = stack.pop()
        for p in rev.get(cur, []):
            if p not in seen:
                seen.add(p)
                stack.append(p)
    return seen


def _forward_reachable_from(trigger_id: str, connections: "ad.flows.Connections") -> set[str]:
    """All node ids reachable from ``trigger_id`` following ``main`` edges forward."""

    seen: set[str] = {trigger_id}
    q: collections.deque[str] = collections.deque([trigger_id])
    while q:
        cur = q.popleft()
        typed = (connections or {}).get(cur) or {}
        for slot in typed.get("main") or []:
            if not slot:
                continue
            for conn in slot:
                if conn.dest_node_id not in seen:
                    seen.add(conn.dest_node_id)
                    q.append(conn.dest_node_id)
    return seen


def trigger_forward_reachable_nodes(trigger_id: str, connections: "ad.flows.Connections") -> frozenset[str]:
    """
    Node ids reachable forward from ``trigger_id`` along ``main`` edges, including ``trigger_id``.

    Used to scope ``pin_data`` injection so a run rooted at one trigger does not fabricate
    ``run_data`` for pinned nodes on another trigger's branch.
    """

    return frozenset(_forward_reachable_from(trigger_id, connections))


def merge_wired_input_indices(
    connections: "ad.flows.Connections",
    *,
    allowed_nodes: AbstractSet[str] | None = None,
) -> dict[str, frozenset[int]]:
    """
    For each destination node, input slot indices that have at least one incoming ``main`` edge.

    Merge nodes with optional ports (e.g. ``docrouter.llm_run``) must wait for every wired slot
    before executing, not only ``min_inputs`` slots — otherwise a fast branch can run the merge
    before a slower parallel branch delivers data to a connected optional port.
    """

    wired: dict[str, set[int]] = {}
    for src, typed in (connections or {}).items():
        if allowed_nodes is not None and src not in allowed_nodes:
            continue
        for slot in (typed or {}).get("main") or []:
            if not slot:
                continue
            for conn in slot:
                dest = conn.dest_node_id
                if allowed_nodes is not None and dest not in allowed_nodes:
                    continue
                wired.setdefault(dest, set()).add(int(conn.index))
    return {node_id: frozenset(indices) for node_id, indices in wired.items()}


def _merge_wired_slots_ready(
    waiting: list[list["ad.flows.FlowItem"] | None],
    required_indices: frozenset[int],
) -> bool:
    """True when every wired input slot has received at least one batch of items."""

    if not required_indices:
        return bool(waiting) and waiting[0] is not None
    for idx in required_indices:
        if idx >= len(waiting) or waiting[idx] is None:
            return False
    return True


def _merge_required_input_indices(
    node_id: str,
    node_type: Any,
    merge_wired_inputs: dict[str, frozenset[int]],
) -> frozenset[int]:
    """Input slots a merge node must wait for before executing (wired ports, else ``min_inputs``)."""

    wired = merge_wired_inputs.get(node_id)
    if wired:
        return wired
    return frozenset(range(max(int(node_type.min_inputs), 1)))


def upstream_closure_for_target(
    trigger_id: str,
    target_id: str,
    connections: "ad.flows.Connections",
) -> set[str]:
    """
    Nodes that lie on at least one path from ``trigger_id`` to ``target_id`` (inclusive).

    Intersection of (backward from target) and (forward from trigger).
    """

    return _upstream_nodes_reaching_target(target_id, connections) & _forward_reachable_from(
        trigger_id, connections
    )


def resolve_execution_start_trigger(
    *,
    nodes: list[dict[str, Any]],
    connections: "ad.flows.Connections",
    start_trigger_node_id: str | None,
    target_node_id: str | None,
) -> str:
    """
    Choose which trigger node id seeds ``run_flow`` / execute-step overlays.

    * Single trigger: always that node's id (``start_trigger_node_id`` ignored unless wrong).
    * Multiple triggers + ``start_trigger_node_id``: must name a trigger on the revision.
    * Multiple triggers + execute step only: unambiguous ancestor trigger chosen automatically when
      exactly one trigger can reach ``target_node_id``; otherwise ``start_trigger_node_id`` is required.
    * Multiple triggers + full run: ``start_trigger_node_id`` is required.
    """

    nodes_by_id = {str(n["id"]): n for n in nodes if n.get("id") is not None}
    triggers: list[dict[str, Any]] = []
    for n in nodes:
        nid, typ = n.get("id"), n.get("type")
        if not isinstance(nid, str) or not nid or not isinstance(typ, str):
            continue
        try:
            if ad.flows.get(typ).is_trigger:
                triggers.append(n)
        except Exception:
            continue

    if not triggers:
        raise FlowValidationError("Flow has no trigger nodes")

    if len(triggers) == 1:
        only = triggers[0]["id"]
        if isinstance(only, str) and isinstance(start_trigger_node_id, str) and start_trigger_node_id.strip():
            st = start_trigger_node_id.strip()
            if st != only:
                raise FlowValidationError(f"start_trigger_node_id must be the only trigger ({only}), not {st!r}")
        return only

    if isinstance(start_trigger_node_id, str) and start_trigger_node_id.strip():
        st = start_trigger_node_id.strip()
        raw = nodes_by_id.get(st)
        if raw is None:
            raise FlowValidationError(f"start_trigger_node_id not found: {st!r}")
        typ_raw = raw.get("type")
        if not isinstance(typ_raw, str):
            raise FlowValidationError(f"start_trigger_node_id {st!r} has no type")
        try:
            if not ad.flows.get(typ_raw).is_trigger:
                raise FlowValidationError(f"start_trigger_node_id {st!r} is not a trigger node")
        except KeyError:
            raise FlowValidationError(f"Unknown node type for start_trigger_node_id={st!r}") from None
        return st

    if isinstance(target_node_id, str) and target_node_id.strip():
        tgt = target_node_id.strip()
        reaching: list[str] = []
        for t in triggers:
            tid = str(t["id"])
            clo = upstream_closure_for_target(tid, tgt, connections)
            if tgt in clo:
                reaching.append(tid)
        if len(reaching) == 1:
            return reaching[0]
        if not reaching:
            raise FlowValidationError(
                f"target node id {tgt!r} is not reachable from any trigger on this revision"
            )
        raise FlowValidationError(
            "Multiple triggers can reach this target; pass start_trigger_node_id to choose one"
        )

    raise FlowValidationError(
        "Flow has multiple triggers; pass start_trigger_node_id to choose which one starts a full run"
    )


def _seed_entry_is_reusable(entry: Any, node_id: str, dirty: frozenset[str]) -> bool:
    if node_id in dirty:
        return False
    if not isinstance(entry, dict):
        return False
    if entry.get("status") != "success":
        return False
    if entry.get("error"):
        return False
    data = entry.get("data")
    if not isinstance(data, dict):
        return False
    main = data.get("main")
    if not isinstance(main, list):
        return False
    return True


def _checkpoint_entry_is_reusable(entry: Any, node_id: str, completed_nodes: frozenset[str]) -> bool:
    if node_id not in completed_nodes:
        return False
    if not isinstance(entry, dict):
        return False
    if entry.get("status") not in ("success", "skipped"):
        return False
    if entry.get("error"):
        return False
    data = entry.get("data")
    if not isinstance(data, dict):
        return False
    main = data.get("main")
    if not isinstance(main, list):
        return False
    return True


def _coerce_main_to_output_slots(main: list[Any], outputs_count: int) -> list[list["ad.flows.FlowItem"]]:
    out: list[list["ad.flows.FlowItem"]] = []
    for i in range(outputs_count):
        lane = main[i] if i < len(main) else []
        if lane is None:
            lane = []
        if not isinstance(lane, list):
            raise RuntimeError(f"run_data seed lane {i} must be a list")
        out.append([ad.flows.coerce_flow_item(x) for x in lane])
    return out


async def _offload_binary_refs(
    run_data: dict[str, Any],
    execution_id: str,
    analytiq_client: Any,
) -> None:
    """
    Walk in-memory `run_data` and upload any inline `BinaryRef.data` to GridFS `flow_blobs`.

    Mutates `BinaryRef` objects in-place:
    - If `ref.data` is set and `ref.storage_id` is empty, saves bytes to GridFS, sets `storage_id`, clears `data`.
    - If both `data` and `storage_id` are set, clears `data` (treat as already stored).
    """

    for node_id, entry in (run_data or {}).items():
        if not isinstance(entry, dict):
            continue
        data = entry.get("data")
        if not isinstance(data, dict):
            continue
        main = data.get("main")
        if not isinstance(main, list):
            continue
        for slot in main:
            if not isinstance(slot, list):
                continue
            for item_idx, item in enumerate(slot):
                if not isinstance(item, ad.flows.FlowItem):
                    continue
                for prop, ref in (item.binary or {}).items():
                    if not isinstance(ref, ad.flows.BinaryRef):
                        continue
                    if ref.data is not None and ref.storage_id:
                        ref.data = None
                        continue
                    if ref.data is None or ref.storage_id:
                        continue
                    key = f"{execution_id}/{node_id}/{item_idx}/{prop}"
                    ref.file_size = len(ref.data)
                    await ad.mongodb.blob.save_blob_async(
                        analytiq_client,
                        bucket="flow_blobs",
                        key=key,
                        blob=ref.data,
                        metadata={
                            "mime_type": ref.mime_type,
                            "file_name": ref.file_name or "",
                            "file_size": ref.file_size,
                        },
                    )
                    ref.storage_id = f"flow_blobs:{key}"
                    ref.data = None


async def persist_run_data(
    context: "ad.flows.ExecutionContext",
    run_data: dict[str, Any],
    *,
    last_node_executed: str | None = None,
    record_checkpoint: bool = False,
) -> None:
    """Persist full `run_data` for a flow execution (used for incremental progress)."""

    # Allow pure unit tests to execute flows without a Mongo-backed client.
    if context.analytiq_client is None:
        return

    db = ad.common.get_async_db(context.analytiq_client)
    await _offload_binary_refs(run_data, context.execution_id, context.analytiq_client)
    stored = _bson_serialize_run_data(run_data)
    patch: dict[str, Any] = {
        "run_data": stored,
        "last_heartbeat_at": datetime.now(UTC),
    }
    if last_node_executed:
        patch["last_node_executed"] = last_node_executed
    update: dict[str, Any] = {"$set": patch}
    if record_checkpoint and last_node_executed:
        update["$addToSet"] = {"completed_nodes": last_node_executed}
    await db.flow_executions.update_one(
        {"_id": ObjectId(context.execution_id)},
        update,
    )


async def read_stop(context: "ad.flows.ExecutionContext") -> bool:
    """Return whether cooperative stop was requested for this execution."""

    if context.stop_requested:
        return True

    # Allow pure unit tests to execute flows without a Mongo-backed client.
    client = context.analytiq_client
    if client is None or not hasattr(client, "mongodb_async"):
        return False

    try:
        db = ad.common.get_async_db(client)
        doc = await db.flow_executions.find_one(
            {"_id": ObjectId(context.execution_id)},
            {"stop_requested": 1},
        )
        return bool((doc or {}).get("stop_requested"))
    except Exception:
        return False


async def _execute_loop(
    context: "ad.flows.ExecutionContext",
    nodes_by_id: dict[str, Any],
    connections: "ad.flows.Connections",
    pin_data: dict[str, Any] | None,
    work: "collections.deque[_WorkItem]",
    merge_waiting: "dict[str, list[list[ad.flows.FlowItem] | None]]",
    merge_source_waiting: "dict[str, list[list[dict[str, Any]] | None]]",
    *,
    allowed_nodes: set[str] | None = None,
    stop_after_node_id: str | None = None,
    dirty_node_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Inner BFS execution loop shared by `run_flow` and `asyncio.wait_for`."""

    partial = allowed_nodes is not None
    merge_wired_inputs = merge_wired_input_indices(connections, allowed_nodes=allowed_nodes)

    while work or merge_waiting:
        try:
            context.stop_requested = bool(await read_stop(context))
        except Exception:
            pass
        if context.stop_requested:
            return {"status": "stopped"}

        if not work and merge_waiting:
            for node_id, slots in list(merge_waiting.items()):
                if partial and node_id not in allowed_nodes:  # type: ignore[operator]
                    merge_waiting.pop(node_id, None)
                    merge_source_waiting.pop(node_id, None)
                    continue
                node = nodes_by_id[node_id]
                ready_inputs = [(x or []) for x in slots]
                src_slots = merge_source_waiting.get(node_id)
                ready_sources = (
                    [(x or []) for x in src_slots]
                    if src_slots is not None
                    else [[] for _ in ready_inputs]
                )
                work.append(
                    _WorkItem(node_id=node["id"], inputs=ready_inputs, source=ready_sources)
                )
                merge_waiting.pop(node_id, None)
                merge_source_waiting.pop(node_id, None)

        wi = work.popleft()
        node = nodes_by_id[wi.node_id]
        node_type = ad.flows.get(node["type"])
        if getattr(node_type, "tool_provider", False):
            continue
        node_label = ad.flows.node_name(node)
        outputs_count = node_type.outputs
        _execution_refs = {
            "execution_id": context.execution_id,
            "flow_id": context.flow_id,
            "flow_revid": context.flow_revid,
        }

        start = time.time()
        start_datetime = datetime.now(UTC)
        context.execution_index += 1
        execution_index = context.execution_index
        context.active_trace_node_id = node["id"]
        try:
            status = "success"
            error_env = None
            run_source = _work_item_source_record(wi)

            if node.get("disabled"):
                out_lists = _empty_outputs(outputs_count)
                status = "skipped"
            elif pin_data and node["id"] in pin_data:
                pinned = ad.flows.coerce_pin_data_node_output(pin_data[node["id"]])
                out_lists = [pinned] + [[] for _ in range(outputs_count - 1)]
            else:
                entry = context.run_data.get(node["id"])
                if _checkpoint_entry_is_reusable(entry, node["id"], context.completed_nodes):
                    cached = entry
                    main_raw = cached["data"]["main"]
                    if not isinstance(main_raw, list):
                        raise RuntimeError(f"Corrupt checkpoint run_data for node {node_label}: data.main must be a list")
                    out_lists = _coerce_main_to_output_slots(main_raw, outputs_count)
                elif partial and _seed_entry_is_reusable(entry, node["id"], dirty_node_ids):
                    cached = entry
                    main_raw = cached["data"]["main"]
                    if not isinstance(main_raw, list):
                        raise RuntimeError(f"Corrupt seed run_data for node {node_label}: data.main must be a list")
                    out_lists = _coerce_main_to_output_slots(main_raw, outputs_count)
                else:
                    try:
                        if not wi.inputs:
                            resolved_node = {
                                **node,
                                "parameters": ad.flows.resolve_parameters(
                                    node.get("parameters") or {},
                                    item=None,
                                    run_data=context.run_data,
                                    input_context=ad.flows.materialize_input_context([]),
                                    execution_refs=_execution_refs,
                                    revision_nodes=context.revision_nodes,
                                ),
                            }
                            _validate_resolved_params(resolved_node)
                            context.credentials.clear()
                            out_lists = await node_type.execute(context, resolved_node, [])
                            if len(out_lists) != outputs_count:
                                raise RuntimeError(
                                    f"Node {node_label} returned {len(out_lists)} output slots, expected {outputs_count}"
                                )
                        elif all(len(slot) == 0 for slot in wi.inputs):
                            out_lists = _empty_outputs(outputs_count)
                            status = "skipped"
                        elif node_type.is_merge or bool(getattr(node_type, "batch_execute_inputs", False)):
                            # Batch nodes (`is_merge`, or types with batch_execute_inputs): resolve expressions
                            # once per node execution. Provide ``_input`` (see ``materialize_input_context``) with all items
                            # across input slots (see `materialize_input_context`).
                            resolved_node = {
                                **node,
                                "parameters": ad.flows.resolve_parameters(
                                    node.get("parameters") or {},
                                    item=None,
                                    run_data=context.run_data,
                                    input_context=ad.flows.materialize_input_context(wi.inputs),
                                    execution_refs=_execution_refs,
                                    revision_nodes=context.revision_nodes,
                                ),
                            }
                            _validate_resolved_params(resolved_node)
                            context.credentials.clear()
                            out_lists = await node_type.execute(context, resolved_node, wi.inputs)
                            if len(out_lists) != outputs_count:
                                raise RuntimeError(
                                    f"Node {node_label} returned {len(out_lists)} output slots, expected {outputs_count}"
                                )
                        else:
                            # Per-item parameter resolution: evaluate params against each input item.
                            combined: list[list["ad.flows.FlowItem"]] = [[] for _ in range(outputs_count)]
                            stopped_mid_node = False
                            for slot_idx, slot in enumerate(wi.inputs):
                                if stopped_mid_node:
                                    break
                                for item_idx, it in enumerate(slot):
                                    resolved_node = {
                                        **node,
                                        "parameters": ad.flows.resolve_parameters(
                                            node.get("parameters") or {},
                                            item=it,
                                            run_data=context.run_data,
                                            input_context=ad.flows.materialize_input_context(
                                                wi.inputs, input_index=slot_idx, item_index=item_idx
                                            ),
                                            execution_refs=_execution_refs,
                                            revision_nodes=context.revision_nodes,
                                        ),
                                    }
                                    if slot_idx == 0 and item_idx == 0:
                                        _validate_resolved_params(resolved_node)
                                    per_inputs = [[] for _ in range(len(wi.inputs))]
                                    per_inputs[slot_idx] = [it]
                                    context.credentials.clear()
                                    per_out = await node_type.execute(context, resolved_node, per_inputs)
                                    if len(per_out) != outputs_count:
                                        raise RuntimeError(
                                            f"Node {node_label} returned {len(per_out)} output slots, expected {outputs_count}"
                                        )
                                    for oi in range(outputs_count):
                                        for out_item in per_out[oi]:
                                            combined[oi].append(
                                                _with_output_paired_item(
                                                    out_item,
                                                    input_slot=slot_idx,
                                                    input_item_index=item_idx,
                                                )
                                            )
                                    try:
                                        context.stop_requested = bool(await read_stop(context))
                                    except Exception:
                                        pass
                                    if context.stop_requested:
                                        stopped_mid_node = True
                                        break
                            out_lists = combined
                    except Exception as e:
                        on_error = node.get("on_error") or "stop"
                        msg = str(e)
                        include_stack = not isinstance(e, FlowValidationError)
                        error_env = node_error_envelope(
                            e,
                            node_id=node["id"],
                            node_name=node_label,
                            include_stack=include_stack,
                        )
                        if on_error == "continue":
                            out_lists = [
                                [_error_item(node["id"], node_label, msg)]
                            ] + _empty_outputs(outputs_count - 1)
                            status = "error"
                        else:
                            context.run_data[node["id"]] = {
                                "status": "error",
                                "start_time": start_datetime.isoformat(),
                                "execution_time_ms": int((time.time() - start) * 1000),
                                "execution_index": execution_index,
                                "data": {"main": []},
                                "error": error_env,
                                "source": run_source,
                                "logs": (context.node_logs.pop(node["id"], None) if hasattr(context, "node_logs") else None),
                                "trace": pop_node_trace(context, node["id"]),
                            }
                            await persist_run_data(
                                context,
                                context.run_data,
                                last_node_executed=node["id"],
                            )
                            raise

            out_lists = _stamp_outputs_producer_meta(out_lists, producer_node_id=node["id"])

            context.run_data[node["id"]] = {
                "status": status,
                "start_time": start_datetime.isoformat(),
                "execution_time_ms": int((time.time() - start) * 1000),
                "execution_index": execution_index,
                "data": {"main": out_lists},
                "error": error_env,
                "source": run_source,
                "logs": (context.node_logs.pop(node["id"], None) if hasattr(context, "node_logs") else None),
                "trace": pop_node_trace(context, node["id"]),
            }
            await persist_run_data(
                context,
                context.run_data,
                last_node_executed=node["id"],
                record_checkpoint=(status in ("success", "skipped")),
            )

            try:
                context.stop_requested = bool(await read_stop(context))
            except Exception:
                pass
            if context.stop_requested:
                return {"status": "stopped"}

            typed = (connections or {}).get(node["id"]) or {}
            main_slots = typed.get("main") or []

            for out_idx, items in enumerate(out_lists):
                if not items:
                    continue
                slot_conns = main_slots[out_idx] if out_idx < len(main_slots) else None
                if not slot_conns:
                    continue
                for conn in slot_conns:
                    if partial and conn.dest_node_id not in allowed_nodes:  # type: ignore[operator]
                        continue
                    dst = nodes_by_id[conn.dest_node_id]
                    dst_type = ad.flows.get(dst["type"])
                    if dst_type.max_inputs is not None:
                        in_slots_count = dst_type.max_inputs
                    else:
                        in_slots_count = max(conn.index + 1, dst_type.min_inputs)

                    if dst_type.is_merge:
                        waiting = merge_waiting.get(dst["id"])
                        waiting_src = merge_source_waiting.get(dst["id"])
                        if waiting is None:
                            waiting = [None] * in_slots_count
                            merge_waiting[dst["id"]] = waiting
                        if waiting_src is None:
                            waiting_src = [None] * in_slots_count
                            merge_source_waiting[dst["id"]] = waiting_src
                        if conn.index >= len(waiting):
                            waiting.extend([None] * (conn.index - len(waiting) + 1))
                            waiting_src.extend([None] * (conn.index - len(waiting_src) + 1))
                        waiting[conn.index] = items
                        waiting_src[conn.index] = [_source_ref(node["id"], previous_node_output=out_idx)]
                        required = _merge_required_input_indices(
                            dst["id"], dst_type, merge_wired_inputs
                        )
                        if _merge_wired_slots_ready(waiting, required):
                            ready_inputs = [(x or []) for x in waiting]
                            ready_sources = [(x or []) for x in waiting_src]
                            work.append(
                                _WorkItem(
                                    node_id=dst["id"],
                                    inputs=ready_inputs,
                                    source=ready_sources,
                                )
                            )
                            merge_waiting.pop(dst["id"], None)
                            merge_source_waiting.pop(dst["id"], None)
                    else:
                        inp = [[] for _ in range(in_slots_count)]
                        inp[conn.index] = items
                        src_slots = [[] for _ in range(in_slots_count)]
                        src_slots[conn.index] = [_source_ref(node["id"], previous_node_output=out_idx)]
                        work.append(_WorkItem(node_id=dst["id"], inputs=inp, source=src_slots))

            if stop_after_node_id and node["id"] == stop_after_node_id:
                work.clear()
                merge_waiting.clear()
                return {"status": "success"}
        finally:
            context.active_trace_node_id = None

    return {"status": "success"}


def _webhook_node_finish_epoch_ms(entry: Any) -> float:
    """Approximate wall-clock end time (epoch ms) for ordering webhook ``last_node`` picks."""

    if not isinstance(entry, dict):
        return -1.0
    ms = float(entry.get("execution_time_ms") or 0)
    st = entry.get("start_time")
    if isinstance(st, str):
        try:
            base_ms = datetime.fromisoformat(st.replace("Z", "+00:00")).timestamp() * 1000.0
            return base_ms + ms
        except Exception:
            pass
    return ms


def pick_webhook_last_node_id(
    run_data: dict[str, Any],
    revision: dict[str, Any],
    *,
    start_trigger_node_id: str | None = None,
) -> str | None:
    """
    Choose which node's primary-output JSON drives synchronous webhook ``last_node`` HTTP replies.

    Prefer **sink** nodes in the forward subgraph from the trigger (nodes with no outgoing ``main``
    edge to another reachable node). When several sinks ran (parallel branches), pick the sink that
    **finished last** using ``start_time`` + ``execution_time_ms`` — not ``run_data`` insertion order.

    Falls back to the latest-finished node among all reachable executed nodes, then any executed node id.
    """

    nodes: list[dict[str, Any]] = revision.get("nodes") or []
    try:
        connections = ad.flows.coerce_json_connections_to_dataclasses(revision.get("connections"))
    except Exception:
        connections = {}

    trigger_id: str | None = None
    requested_explicit: str | None = None
    if isinstance(start_trigger_node_id, str) and start_trigger_node_id.strip():
        requested_explicit = start_trigger_node_id.strip()
        trig = requested_explicit
        raw_n = None
        for n in nodes:
            if isinstance(n, dict) and str(n.get("id") or "") == trig:
                raw_n = n
                break
        if raw_n is not None:
            typ_raw = raw_n.get("type")
            if isinstance(typ_raw, str):
                try:
                    if ad.flows.get(typ_raw).is_trigger:
                        trigger_id = trig
                except Exception:
                    pass

    if requested_explicit and trigger_id is None:
        logger.warning(
            "pick_webhook_last_node_id: start_trigger_node_id %r did not resolve (missing node, non-trigger type, or registry lookup error); falling back to first trigger or global latest-finished heuristic — ambiguous on multi-trigger flows",
            requested_explicit,
        )

    if not trigger_id:
        for n in nodes:
            if not isinstance(n, dict):
                continue
            nid, typ = n.get("id"), n.get("type")
            if not isinstance(nid, str) or not nid or not isinstance(typ, str):
                continue
            try:
                if ad.flows.get(typ).is_trigger:
                    trigger_id = nid
                    break
            except Exception:
                continue

    def _fallback_latest(keys: list[str]) -> str | None:
        if not keys:
            return None
        return max(keys, key=lambda i: _webhook_node_finish_epoch_ms(run_data.get(i)))

    if not trigger_id:
        fb = [k for k in run_data.keys() if isinstance(k, str) and not k.startswith("_")]
        return _fallback_latest(fb)

    reachable = _forward_reachable_from(trigger_id, connections)

    sinks: list[str] = []
    for nid in reachable:
        typed = (connections or {}).get(nid) or {}
        outgoing_to_reachable = False
        for slot in typed.get("main") or []:
            if not slot:
                continue
            for conn in slot:
                if conn.dest_node_id in reachable:
                    outgoing_to_reachable = True
                    break
            if outgoing_to_reachable:
                break
        if not outgoing_to_reachable:
            sinks.append(nid)

    sink_ran = [s for s in sinks if s in run_data]
    if sink_ran:
        return max(sink_ran, key=lambda i: _webhook_node_finish_epoch_ms(run_data.get(i)))

    reachable_ran = [n for n in reachable if n in run_data]
    if reachable_ran:
        return max(reachable_ran, key=lambda i: _webhook_node_finish_epoch_ms(run_data.get(i)))

    fb = [k for k in run_data.keys() if isinstance(k, str) and not k.startswith("_")]
    return _fallback_latest(fb)


def extract_last_node_output_json(
    run_data: dict[str, Any],
    revision: dict[str, Any],
    *,
    start_trigger_node_id: str | None = None,
) -> Any:
    """
    Return the first primary-output item's ``json`` from the graph sink node chosen
    by ``pick_webhook_last_node_id`` (same heuristic as synchronous webhook ``last_node`` replies).
    """

    last_node_id = pick_webhook_last_node_id(
        run_data, revision, start_trigger_node_id=start_trigger_node_id
    )
    if not isinstance(last_node_id, str):
        return None
    ent = run_data.get(last_node_id) or {}
    try:
        main = ent.get("data", {}).get("main")  # type: ignore[union-attr]
        if isinstance(main, list) and main and isinstance(main[0], list) and main[0]:
            it = main[0][0]
            if isinstance(it, dict):
                return it.get("json")
            if hasattr(it, "json"):
                return it.json
    except Exception:
        pass
    return None


async def run_flow(
    *,
    context: "ad.flows.ExecutionContext",
    revision: dict[str, Any],
    target_node_id: str | None = None,
    dirty_node_ids: frozenset[str] | None = None,
    start_trigger_node_id: str | None = None,
) -> dict[str, Any]:
    """
    Run a single flow execution for a specific immutable revision snapshot.

    Returns a small status dict (e.g. `{"status": "success" | "stopped"}`).
    """

    nodes: list[dict[str, Any]] = revision.get("nodes") or []
    connections: "ad.flows.Connections" = ad.flows.coerce_json_connections_to_dataclasses(
        revision.get("connections")
    )
    settings: dict[str, Any] = revision.get("settings") or {}
    revision_pin_data: dict[str, Any] | None = revision.get("pin_data")

    validate_revision(nodes, connections, settings, revision_pin_data)

    pin_data: dict[str, Any] | None = (
        revision_pin_data if pin_data_enabled_for_mode(context.mode) else None
    )

    context.revision_nodes = nodes

    from analytiq_data.flows.tool_wiring import tool_consumer_wiring

    # Rebuild wiring for runtime dispatch (parameters validated at save time in validate_tool_graph).
    context.tool_consumer_wiring = tool_consumer_wiring(nodes, connections)

    nodes_by_id = {n["id"]: n for n in nodes}
    chosen_trigger_id = resolve_execution_start_trigger(
        nodes=nodes,
        connections=connections,
        start_trigger_node_id=start_trigger_node_id,
        target_node_id=target_node_id,
    )
    dirty = dirty_node_ids or frozenset()

    merge_waiting: dict[str, list[list["ad.flows.FlowItem"] | None]] = {}
    merge_source_waiting: dict[str, list[list[dict[str, Any]] | None]] = {}
    work: collections.deque[_WorkItem] = collections.deque(
        [_WorkItem(node_id=chosen_trigger_id, inputs=[], source=[])]
    )

    if target_node_id:
        if target_node_id not in nodes_by_id:
            raise FlowValidationError(f"target_node_id not found in revision: {target_node_id}")
        closure = upstream_closure_for_target(chosen_trigger_id, target_node_id, connections)
        if target_node_id not in closure:
            raise FlowValidationError(
                f"target node {ad.flows.node_name(nodes_by_id[target_node_id])} is not reachable from the "
                "selected trigger on this revision"
            )
        coro = _execute_loop(
            context,
            nodes_by_id,
            connections,
            pin_data,
            work,
            merge_waiting,
            merge_source_waiting,
            allowed_nodes=closure,
            stop_after_node_id=target_node_id,
            dirty_node_ids=dirty,
        )
    else:
        coro = _execute_loop(
            context,
            nodes_by_id,
            connections,
            pin_data,
            work,
            merge_waiting,
            merge_source_waiting,
        )

    timeout = settings.get("execution_timeout_seconds")
    if timeout:
        return await asyncio.wait_for(coro, timeout=float(timeout))
    return await coro

