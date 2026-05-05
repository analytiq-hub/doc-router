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
from typing import AbstractSet, Any

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
            raise FlowValidationError(f"Node {ad.flows.node_name(n)} is not reachable from trigger")

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
        return {
            "mime_type": obj.mime_type,
            "file_name": obj.file_name,
            "storage_id": obj.storage_id,
        }
    if isinstance(obj, list):
        return [_bson_serialize_value(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _bson_serialize_value(v) for k, v in obj.items()}
    return obj


def _bson_serialize_run_data(run_data: dict[str, Any]) -> dict[str, Any]:
    return {k: _bson_serialize_value(v) for k, v in run_data.items()}


def apply_revision_pins_to_run_data(
    run_data: dict[str, Any],
    revision: dict[str, Any],
    *,
    allowed_node_ids: AbstractSet[str] | None = None,
) -> set[str]:
    """
    Inject or replace ``run_data[node_id]`` with a pinned output snapshot **before** the engine loop.

    Execute-step merges prior ``initial_run_data`` into ``run_data``; without this, seeded merge
    (or branch) snapshots can contradict ``revision.pin_data``. Pinned lane-0 output wins for nodes
    in scope (execute-step subgraph when ``allowed_node_ids`` is set; entire revision otherwise).

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
                    await ad.blob.save_blob_async(
                        analytiq_client,
                        bucket="flow_blobs",
                        key=key,
                        blob=ref.data,
                        metadata={"mime_type": ref.mime_type, "file_name": ref.file_name or ""},
                    )
                    ref.storage_id = f"flow_blobs:{key}"
                    ref.data = None


async def persist_run_data(context: "ad.flows.ExecutionContext", run_data: dict[str, Any]) -> None:
    """Persist full `run_data` for a flow execution (used for incremental progress)."""

    # Allow pure unit tests to execute flows without a Mongo-backed client.
    if context.analytiq_client is None:
        return

    db = ad.common.get_async_db(context.analytiq_client)
    await _offload_binary_refs(run_data, context.execution_id, context.analytiq_client)
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
    *,
    allowed_nodes: set[str] | None = None,
    stop_after_node_id: str | None = None,
    dirty_node_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Inner BFS execution loop shared by `run_flow` and `asyncio.wait_for`."""

    partial = allowed_nodes is not None

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
                    continue
                node = nodes_by_id[node_id]
                ready_inputs = [(x or []) for x in slots]
                work.append(_WorkItem(node_id=node["id"], inputs=ready_inputs))
                merge_waiting.pop(node_id, None)

        wi = work.popleft()
        node = nodes_by_id[wi.node_id]
        node_type = ad.flows.get(node["type"])
        node_label = ad.flows.node_name(node)
        outputs_count = node_type.outputs
        _execution_refs = {
            "execution_id": context.execution_id,
            "flow_id": context.flow_id,
            "flow_revid": context.flow_revid,
        }

        start = time.time()
        start_datetime = datetime.now(UTC)
        status = "success"
        error_env = None

        if node.get("disabled"):
            out_lists = _empty_outputs(outputs_count)
            status = "skipped"
        elif pin_data and node["id"] in pin_data:
            pinned = ad.flows.coerce_pin_data_node_output(pin_data[node["id"]])
            out_lists = [pinned] + [[] for _ in range(outputs_count - 1)]
        elif partial and _seed_entry_is_reusable(context.run_data.get(node["id"]), node["id"], dirty_node_ids):
            cached = context.run_data[node["id"]]
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
                                combined[oi].extend(per_out[oi])
                    out_lists = combined
            except Exception as e:
                on_error = node.get("on_error") or "stop"
                msg = str(e)
                error_env = {
                    "message": msg,
                    "node_id": node["id"],
                    "node_name": node_label,
                    "stack": None,
                }
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

        if stop_after_node_id and node["id"] == stop_after_node_id:
            work.clear()
            merge_waiting.clear()
            return {"status": "success"}

    return {"status": "success"}


async def run_flow(
    *,
    context: "ad.flows.ExecutionContext",
    revision: dict[str, Any],
    target_node_id: str | None = None,
    dirty_node_ids: frozenset[str] | None = None,
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
    pin_data: dict[str, Any] | None = revision.get("pin_data")

    validate_revision(nodes, connections, settings, pin_data)

    context.revision_nodes = nodes

    nodes_by_id = {n["id"]: n for n in nodes}
    trigger = next(n for n in nodes if ad.flows.get(n["type"]).is_trigger)
    dirty = dirty_node_ids or frozenset()

    merge_waiting: dict[str, list[list["ad.flows.FlowItem"] | None]] = {}
    work: collections.deque[_WorkItem] = collections.deque([_WorkItem(node_id=trigger["id"], inputs=[])])

    if target_node_id:
        if target_node_id not in nodes_by_id:
            raise FlowValidationError(f"target_node_id not found in revision: {target_node_id}")
        closure = upstream_closure_for_target(trigger["id"], target_node_id, connections)
        if target_node_id not in closure:
            raise FlowValidationError(
                f"target node {ad.flows.node_name(nodes_by_id[target_node_id])} is not reachable from the trigger "
                "on this revision"
            )
        coro = _execute_loop(
            context,
            nodes_by_id,
            connections,
            pin_data,
            work,
            merge_waiting,
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
        )

    timeout = settings.get("execution_timeout_seconds")
    if timeout:
        return await asyncio.wait_for(coro, timeout=float(timeout))
    return await coro

