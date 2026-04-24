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
import time
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any

from bson import ObjectId
from jsonschema import Draft7Validator

import analytiq_data as ad


class FlowValidationError(ValueError):
    """Raised when a flow revision fails validation (schema, graph, or registry rules)."""

    pass


def canonical_graph_hash(
    nodes: list[dict[str, Any]], connections: "ad.flows.Connections", settings: dict[str, Any]
) -> str:
    """Return a stable SHA-256 hash of the flow graph for dedup/version checks."""

    payload = {"nodes": nodes, "connections": connections, "settings": settings}
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
                if conn.dest_node_id in node_ids:
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

    Enforces uniqueness (ids/names), existence of referenced nodes, port index
    bounds, DAG constraint, exactly one trigger, reachability, and JSON-schema
    parameter validation via the registered node types.
    """

    settings = settings or {}
    node_ids = [n.get("id") for n in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise FlowValidationError("nodes[].id must be unique")

    node_names = [n.get("name") for n in nodes]
    if len(node_names) != len(set(node_names)):
        raise FlowValidationError("nodes[].name must be unique")

    nodes_by_id = {n["id"]: n for n in nodes}

    # Exactly one trigger node.
    trigger_nodes = []
    for n in nodes:
        try:
            nt = ad.flows.get(n["type"])
        except KeyError:
            raise FlowValidationError(f"Unknown node type: {n['type']}") from None
        if nt.is_trigger:
            trigger_nodes.append(n)
    if len(trigger_nodes) != 1:
        raise FlowValidationError(f"Flow must contain exactly one trigger node (found {len(trigger_nodes)})")

    # Reachability from trigger.
    trigger_id = trigger_nodes[0]["id"]
    reachable = {trigger_id}
    frontier = [trigger_id]
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
        if n["id"] == trigger_id:
            continue
        if n["id"] not in reachable:
            raise FlowValidationError(f"Node {n['id']} is not reachable from trigger")

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
                raise FlowValidationError(f"Source node {src} output index out of range: {out_idx}")
            if not slot:
                continue
            for conn in slot:
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
                        f"Connection destination index out of range for node {conn.dest_node_id}: {conn.index}"
                    )
                if conn.index >= max(dst_type.min_inputs, (dst_type.max_inputs or conn.index + 1)):
                    # Best-effort; for unbounded max_inputs we accept any index >= 0.
                    if dst_type.max_inputs is not None:
                        raise FlowValidationError(
                            f"Connection destination index out of range for node {conn.dest_node_id}: {conn.index}"
                        )

    # Acyclic.
    _toposort(nodes, connections or {})

    # Parameter validation.
    for n in nodes:
        try:
            nt = ad.flows.get(n["type"])
        except KeyError:
            raise FlowValidationError(f"Unknown node type: {n['type']}") from None
        params = n.get("parameters") or {}
        try:
            Draft7Validator(nt.parameter_schema).validate(params)
        except Exception as e:
            raise FlowValidationError(f"Invalid parameters for node {n['id']} ({nt.key}): {e}") from e
        extra = []
        try:
            extra = nt.validate_parameters(params) or []
        except Exception as e:
            raise FlowValidationError(f"validate_parameters failed for node {n['id']} ({nt.key}): {e}") from e
        if extra:
            raise FlowValidationError(f"Invalid parameters for node {n['id']} ({nt.key}): {extra}")

    if pin_data:
        for node_id in pin_data.keys():
            if node_id not in nodes_by_id:
                raise FlowValidationError(f"pin_data references unknown node id: {node_id}")


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
        return {
            "mime_type": obj.mime_type,
            "file_name": obj.file_name,
            "data": obj.data,
            "storage_id": obj.storage_id,
        }
    if isinstance(obj, list):
        return [_bson_serialize_value(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _bson_serialize_value(v) for k, v in obj.items()}
    return obj


def _bson_serialize_run_data(run_data: dict[str, Any]) -> dict[str, Any]:
    return {k: _bson_serialize_value(v) for k, v in run_data.items()}


async def persist_run_data(context: "ad.flows.ExecutionContext", run_data: dict[str, Any]) -> None:
    """Persist full `run_data` for a flow execution (used for incremental progress)."""

    # Allow pure unit tests to execute flows without a Mongo-backed client.
    if context.analytiq_client is None:
        return

    db = ad.common.get_async_db(context.analytiq_client)
    stored = _bson_serialize_run_data(run_data)
    await db.flow_executions.update_one(
        {"_id": ObjectId(context.execution_id)},
        {
            "$set": {
                "run_data": stored,
                "last_heartbeat_at": datetime.now(UTC),
            }
        },
    )


async def read_stop(context: "ad.flows.ExecutionContext") -> bool:
    """Return whether cooperative stop was requested for this execution."""

    # Allow pure unit tests to execute flows without a Mongo-backed client.
    if context.analytiq_client is None:
        return False

    db = ad.common.get_async_db(context.analytiq_client)
    doc = await db.flow_executions.find_one(
        {"_id": ObjectId(context.execution_id)},
        {"stop_requested": 1},
    )
    return bool((doc or {}).get("stop_requested"))


async def _execute_loop(
    context: "ad.flows.ExecutionContext",
    nodes_by_id: dict[str, Any],
    connections: "ad.flows.Connections",
    pin_data: dict[str, Any] | None,
    work: "collections.deque[_WorkItem]",
    merge_waiting: "dict[str, list[list[ad.flows.FlowItem] | None]]",
) -> dict[str, Any]:
    """Inner BFS execution loop shared by `run_flow` and `asyncio.wait_for`."""

    while work or merge_waiting:
        try:
            context.stop_requested = bool(await read_stop(context))
        except Exception:
            pass
        if context.stop_requested:
            return {"status": "stopped"}

        if not work and merge_waiting:
            for node_id, slots in list(merge_waiting.items()):
                node = nodes_by_id[node_id]
                ready_inputs = [(x or []) for x in slots]
                work.append(_WorkItem(node_id=node["id"], inputs=ready_inputs))
                merge_waiting.pop(node_id, None)

        wi = work.popleft()
        node = nodes_by_id[wi.node_id]
        node_type = ad.flows.get(node["type"])
        outputs_count = node_type.outputs

        start = time.time()
        start_datetime = datetime.now(UTC)
        status = "success"
        error_env = None

        if node.get("disabled"):
            out_lists = _empty_outputs(outputs_count)
            status = "skipped"
        elif pin_data and node["id"] in pin_data:
            pinned = ad.flows.coerce_flow_item_list(pin_data[node["id"]] or [])
            out_lists = [pinned] + [[] for _ in range(outputs_count - 1)]
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
                        ),
                    }
                    out_lists = await node_type.execute(context, resolved_node, [])
                    if len(out_lists) != outputs_count:
                        raise RuntimeError(
                            f"Node {node['id']} returned {len(out_lists)} output slots, expected {outputs_count}"
                        )
                elif all(len(slot) == 0 for slot in wi.inputs):
                    out_lists = _empty_outputs(outputs_count)
                    status = "skipped"
                elif node_type.is_merge:
                    # Merge nodes resolve expressions once per node execution. Provide an n8n-ish
                    # `$input` object containing all items across input slots.
                    resolved_node = {
                        **node,
                        "parameters": ad.flows.resolve_parameters(
                            node.get("parameters") or {},
                            item=None,
                            run_data=context.run_data,
                            input_context=ad.flows.materialize_input_context(wi.inputs),
                        ),
                    }
                    out_lists = await node_type.execute(context, resolved_node, wi.inputs)
                    if len(out_lists) != outputs_count:
                        raise RuntimeError(
                            f"Node {node['id']} returned {len(out_lists)} output slots, expected {outputs_count}"
                        )
                else:
                    # n8n-style per-item parameter resolution: evaluate params against each input item.
                    combined: list[list["ad.flows.FlowItem"]] = [[] for _ in range(outputs_count)]
                    for slot_idx, slot in enumerate(wi.inputs):
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
                                ),
                            }
                            per_inputs = [[] for _ in range(len(wi.inputs))]
                            per_inputs[slot_idx] = [it]
                            per_out = await node_type.execute(context, resolved_node, per_inputs)
                            if len(per_out) != outputs_count:
                                raise RuntimeError(
                                    f"Node {node['id']} returned {len(per_out)} output slots, expected {outputs_count}"
                                )
                            for oi in range(outputs_count):
                                combined[oi].extend(per_out[oi])
                    out_lists = combined
            except Exception as e:
                on_error = node.get("on_error") or "stop"
                msg = str(e)
                error_env = {
                    "message": msg,
                    "node_id": node["id"],
                    "node_name": node.get("name") or node_type.label,
                    "stack": None,
                }
                if on_error == "continue":
                    out_lists = [
                        [_error_item(node["id"], node.get("name") or node_type.label, msg)]
                    ] + _empty_outputs(outputs_count - 1)
                    status = "error"
                else:
                    context.run_data[node["id"]] = {
                        "status": "error",
                        "start_time": start_datetime.isoformat(),
                        "execution_time_ms": int((time.time() - start) * 1000),
                        "data": {"main": []},
                        "error": error_env,
                    }
                    await persist_run_data(context, context.run_data)
                    raise

        context.run_data[node["id"]] = {
            "status": status,
            "start_time": start_datetime.isoformat(),
            "execution_time_ms": int((time.time() - start) * 1000),
            "data": {"main": out_lists},
            "error": error_env,
        }
        await persist_run_data(context, context.run_data)

        typed = (connections or {}).get(node["id"]) or {}
        main_slots = typed.get("main") or []

        for out_idx, items in enumerate(out_lists):
            if not items:
                continue
            slot_conns = main_slots[out_idx] if out_idx < len(main_slots) else None
            if not slot_conns:
                continue
            for conn in slot_conns:
                dst = nodes_by_id[conn.dest_node_id]
                dst_type = ad.flows.get(dst["type"])
                if dst_type.max_inputs is not None:
                    in_slots_count = dst_type.max_inputs
                else:
                    in_slots_count = max(conn.index + 1, dst_type.min_inputs)

                if dst_type.is_merge:
                    waiting = merge_waiting.get(dst["id"])
                    if waiting is None:
                        waiting = [None] * in_slots_count
                        merge_waiting[dst["id"]] = waiting
                    if conn.index >= len(waiting):
                        waiting.extend([None] * (conn.index - len(waiting) + 1))
                    waiting[conn.index] = items
                    if all(x is not None for x in waiting[: max(dst_type.min_inputs, 1)]):
                        ready_inputs = [(x or []) for x in waiting]
                        work.append(_WorkItem(node_id=dst["id"], inputs=ready_inputs))
                        merge_waiting.pop(dst["id"], None)
                else:
                    inp = [[] for _ in range(in_slots_count)]
                    inp[conn.index] = items
                    work.append(_WorkItem(node_id=dst["id"], inputs=inp))

    return {"status": "success"}


async def run_flow(*, context: "ad.flows.ExecutionContext", revision: dict[str, Any]) -> dict[str, Any]:
    """
    Run a single flow execution for a specific immutable revision snapshot.

    Returns a small status dict (e.g. `{"status": "success" | "stopped"}`).
    """

    nodes: list[dict[str, Any]] = revision.get("nodes") or []
    connections: "ad.flows.Connections" = ad.flows.coerce_json_connections_to_dataclasses(
        revision.get("connections")
    )
    settings: dict[str, Any] = revision.get("settings") or {}
    pin_data: dict[str, Any] | None = revision.get("pin_data")

    validate_revision(nodes, connections, settings, pin_data)

    nodes_by_id = {n["id"]: n for n in nodes}
    trigger = next(n for n in nodes if ad.flows.get(n["type"]).is_trigger)

    merge_waiting: dict[str, list[list["ad.flows.FlowItem"] | None]] = {}
    work: collections.deque[_WorkItem] = collections.deque([_WorkItem(node_id=trigger["id"], inputs=[])])

    timeout = settings.get("execution_timeout_seconds")
    coro = _execute_loop(context, nodes_by_id, connections, pin_data, work, merge_waiting)
    if timeout:
        return await asyncio.wait_for(coro, timeout=float(timeout))
    return await coro

