"""Tool graph analysis: wire tool providers to consumers and build registries."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import analytiq_data as ad

from .errors import FlowValidationError
from .port_types import FLOWS_TOOL_CONNECTION_TYPE

_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

_KB_TOOL_PARAMETERS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search query to find relevant information in the knowledge base",
        },
        "top_k": {
            "type": "integer",
            "description": "Number of results to return (default: 5)",
        },
        "metadata_filter": {
            "type": "object",
            "description": "Optional metadata filters (document_name, tag_ids, etc.)",
        },
        "coalesce_neighbors": {
            "type": "integer",
            "description": "Number of neighboring chunks to include for context (default: from KB config)",
        },
    },
    "required": ["query"],
}


class UnknownToolError(KeyError):
    """Raised when the LLM or executor references a tool name that is not wired."""


@dataclass
class WiredTool:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    node_id: str
    node_type: str
    node: dict[str, Any]


class WiredToolRegistry:
    def __init__(self, tools: list[WiredTool]) -> None:
        self._by_name = {t.name: t for t in tools}
        self.tools = list(tools)

    def openai_definitions(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for t in self.tools:
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters_schema,
                    },
                }
            )
        return out

    def resolve(self, name: str) -> WiredTool:
        if name not in self._by_name:
            raise UnknownToolError(f"Unknown tool: {name}")
        return self._by_name[name]


def _slugify_kb_name(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:48] if s else "kb")


def default_kb_tool_name(kb_display_name: str, *, used: set[str]) -> str:
    base = f"search_{_slugify_kb_name(kb_display_name)}"
    if base not in used:
        return base
    n = 2
    while f"{base}_{n}" in used:
        n += 1
    return f"{base}_{n}"


def _tool_edges(connections: "ad.flows.Connections") -> list[tuple[str, Any]]:
    """Return (source_node_id, NodeConnection) for every flows.tool edge."""

    edges: list[tuple[str, Any]] = []
    for src, typed in (connections or {}).items():
        for slot in ad.flows.main_connection_slots(typed):
            if not slot:
                continue
            for conn in slot:
                if conn.connection_type == FLOWS_TOOL_CONNECTION_TYPE:
                    edges.append((src, conn))
    return edges


def _build_wired_tool(node: dict[str, Any], node_type: Any) -> WiredTool:
    params = node.get("parameters") or {}
    key = node_type.key

    if key == "flows.tool_code":
        name = str(params.get("tool_name") or "").strip()
        description = str(params.get("tool_description") or "").strip()
        schema = params.get("parameters_schema")
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
    elif key == "flows.kb_tool":
        name = str(params.get("tool_name") or "").strip()
        description = str(params.get("tool_description") or "").strip()
        schema = dict(_KB_TOOL_PARAMETERS_SCHEMA)
    elif key == "flows.flow_tool":
        name = str(params.get("tool_name") or "").strip()
        description = str(params.get("tool_description") or "").strip()
        schema = params.get("parameters_schema")
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
    else:
        raise FlowValidationError(f"Node {ad.flows.node_name(node)} is not a tool provider ({key})")

    if not name or not _TOOL_NAME_RE.match(name):
        raise FlowValidationError(
            f"Tool node {ad.flows.node_name(node)} has invalid tool_name {name!r}"
        )
    if not description:
        raise FlowValidationError(f"Tool node {ad.flows.node_name(node)} requires tool_description")

    if schema.get("type") != "object":
        raise FlowValidationError(
            f"Tool node {ad.flows.node_name(node)} parameters_schema must be type object"
        )

    return WiredTool(
        name=name,
        description=description,
        parameters_schema=schema,
        node_id=str(node["id"]),
        node_type=key,
        node=node,
    )


def tool_consumer_wiring(
    nodes: list[dict[str, Any]],
    connections: "ad.flows.Connections",
) -> dict[str, list[WiredTool]]:
    """Map tool_consumer node_id -> ordered wired tools (by connection index)."""

    nodes_by_id = {n["id"]: n for n in nodes}
    consumer_tools: dict[str, list[tuple[int, WiredTool]]] = {}

    for src_id, conn in _tool_edges(connections):
        dst_id = conn.dest_node_id
        if src_id not in nodes_by_id or dst_id not in nodes_by_id:
            continue
        src_node = nodes_by_id[src_id]
        dst_node = nodes_by_id[dst_id]
        src_type = ad.flows.get(src_node["type"])
        dst_type = ad.flows.get(dst_node["type"])
        if not getattr(src_type, "tool_provider", False):
            continue
        if not getattr(dst_type, "tool_consumer", False):
            continue
        wired = _build_wired_tool(src_node, src_type)
        consumer_tools.setdefault(dst_id, []).append((int(conn.index), wired))

    out: dict[str, list[WiredTool]] = {}
    for consumer_id, pairs in consumer_tools.items():
        pairs.sort(key=lambda x: x[0])
        out[consumer_id] = [t for _, t in pairs]
    return out


def _validate_tool_provider_params(node: dict[str, Any], node_type: Any) -> None:
    """Validate tool_name, description, and schema on every tool_provider node (save time)."""

    if not getattr(node_type, "tool_provider", False):
        return
    _build_wired_tool(node, node_type)


def validate_tool_graph(
    nodes: list[dict[str, Any]],
    connections: "ad.flows.Connections",
) -> None:
    """Validate tool_provider / tool_consumer wiring rules.

    Authoritative gate for wired-tool metadata: ``tool_consumer_wiring`` (and
    ``_build_wired_tool``) runs here at save time. ``run_flow`` rebuilds wiring
    from the same revision without re-validating parameters.
    """

    nodes_by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        nt = ad.flows.get(n["type"])
        _validate_tool_provider_params(n, nt)

    tool_edges = _tool_edges(connections)
    consumers_of: dict[str, set[str]] = {}

    for src_id, conn in tool_edges:
        if src_id not in nodes_by_id:
            raise FlowValidationError(f"Tool connection source node does not exist: {src_id}")
        if conn.dest_node_id not in nodes_by_id:
            raise FlowValidationError(f"Tool connection destination node does not exist: {conn.dest_node_id}")

        src_node = nodes_by_id[src_id]
        dst_node = nodes_by_id[conn.dest_node_id]
        src_type = ad.flows.get(src_node["type"])
        dst_type = ad.flows.get(dst_node["type"])

        if conn.connection_type != FLOWS_TOOL_CONNECTION_TYPE:
            continue

        if not getattr(src_type, "tool_provider", False):
            raise FlowValidationError(
                f"Node {ad.flows.node_name(src_node)} cannot emit flows.tool connections"
            )
        if not getattr(dst_type, "tool_consumer", False):
            raise FlowValidationError(
                f"Node {ad.flows.node_name(dst_node)} does not accept flows.tool connections"
            )
        consumers_of.setdefault(src_id, set()).add(conn.dest_node_id)

    for n in nodes:
        nt = ad.flows.get(n["type"])
        if getattr(nt, "tool_provider", False):
            if nt.min_inputs != 0 or (nt.max_inputs not in (0, None)):
                raise FlowValidationError(
                    f"Tool provider {ad.flows.node_name(n)} must have no main inputs"
                )
            wired = consumers_of.get(n["id"]) or set()
            if not wired:
                raise FlowValidationError(
                    f"Tool node {ad.flows.node_name(n)} must connect to an AI Agent or Tool Executor"
                )

    wiring = tool_consumer_wiring(nodes, connections)
    for consumer_id, tools in wiring.items():
        names = [t.name for t in tools]
        if len(names) != len(set(names)):
            dupes = sorted({x for x in names if names.count(x) > 1})
            consumer = nodes_by_id[consumer_id]
            raise FlowValidationError(
                f"Duplicate tool name(s) on {ad.flows.node_name(consumer)}: {', '.join(dupes)}"
            )


def example_arguments_from_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Build a default arguments object from a JSON Schema (Path B test modal)."""

    if not isinstance(schema, dict) or schema.get("type") != "object":
        return {}
    props = schema.get("properties")
    if not isinstance(props, dict):
        return {}
    required = schema.get("required")
    req_set = set(required) if isinstance(required, list) else set()
    out: dict[str, Any] = {}
    for key, spec in props.items():
        if not isinstance(spec, dict):
            continue
        if "default" in spec:
            out[key] = spec["default"]
        elif key in req_set:
            t = spec.get("type")
            if t == "string":
                out[key] = ""
            elif t == "integer":
                out[key] = 0
            elif t == "number":
                out[key] = 0.0
            elif t == "boolean":
                out[key] = False
            elif t == "object":
                out[key] = {}
            elif t == "array":
                out[key] = []
    return out


TOOL_TEST_MANUAL_ID = "__tool_test_manual__"
TOOL_TEST_EXECUTOR_ID = "__tool_test_executor__"


def tool_arguments_schema_for_node(node: dict[str, Any]) -> dict[str, Any]:
    """JSON Schema for Path B test-arguments modal defaults."""

    node_type = ad.flows.get(node["type"])
    return _build_wired_tool(node, node_type).parameters_schema


def prepare_tool_test_run(
    *,
    revision: dict[str, Any],
    tool_node_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> tuple[dict[str, Any], str, str]:
    """
    Rewire an in-memory revision for Path B execute-step on a tool_provider node.

    Returns ``(revision, start_trigger_node_id, run_target_node_id)`` where
    ``run_target_node_id`` is the synthetic Tool Executor (main-path target).
    The client ``target_node_id`` on the execution doc stays the real tool node id for UI focus.
    """

    nodes = list(revision.get("nodes") or [])
    connections = ad.flows.coerce_json_connections_to_dataclasses(revision.get("connections"))
    new_nodes, new_connections, executor_id = rewire_graph_for_tool_test(
        nodes=nodes,
        connections=connections,
        tool_node_id=tool_node_id,
        tool_name=tool_name,
        arguments=arguments,
    )
    revision_out = {
        **revision,
        "nodes": new_nodes,
        "connections": new_connections,
    }
    return revision_out, TOOL_TEST_MANUAL_ID, executor_id


def rewire_graph_for_tool_test(
    *,
    nodes: list[dict[str, Any]],
    connections: "ad.flows.Connections",
    tool_node_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> tuple[list[dict[str, Any]], "ad.flows.Connections", str]:
    """
    Path B: synthetic in-memory graph for execute-step on a tool_provider node.

    Returns (nodes, connections, synthetic_executor_node_id).
    """

    nodes_by_id = {n["id"]: n for n in nodes}
    if tool_node_id not in nodes_by_id:
        raise FlowValidationError(f"Tool node not found: {tool_node_id}")

    tool_node = nodes_by_id[tool_node_id]
    tool_type = ad.flows.get(tool_node["type"])
    if not getattr(tool_type, "tool_provider", False):
        raise FlowValidationError(f"Node {ad.flows.node_name(tool_node)} is not a tool provider")

    wiring = tool_consumer_wiring(nodes, connections)
    consumer_id: str | None = None
    for cid, tools in wiring.items():
        if any(t.node_id == tool_node_id for t in tools):
            consumer_id = cid
            break
    if consumer_id is None:
        raise FlowValidationError(
            f"Tool node {ad.flows.node_name(tool_node)} is not wired to a tool consumer"
        )

    manual_id = TOOL_TEST_MANUAL_ID
    executor_id = TOOL_TEST_EXECUTOR_ID
    manual_node = {
        "id": manual_id,
        "name": "Tool test (manual)",
        "type": "flows.trigger.manual",
        "position": [0, 0],
        "parameters": {},
        "disabled": False,
        "on_error": "stop",
    }
    executor_node = {
        "id": executor_id,
        "name": "Tool test (executor)",
        "type": "flows.tool_executor",
        "position": [0, 0],
        "parameters": {
            "tool_name": tool_name,
            "arguments_source": "fixed",
            "arguments": arguments,
            "mode": "per_item",
        },
        "disabled": False,
        "on_error": "stop",
    }

    new_nodes = list(nodes) + [manual_node, executor_node]
    new_connections: dict[str, Any] = {}
    for src, typed in (connections or {}).items():
        new_connections[src] = typed

    from analytiq_data.flows.connections import NodeConnection

    new_connections[manual_id] = {
        "main": [[NodeConnection(dest_node_id=executor_id, connection_type="main", index=0)]]
    }

    # Rewire tool edge to synthetic executor instead of original consumer.
    rewired = False
    for src, typed in list(new_connections.items()):
        main_slots = list(ad.flows.main_connection_slots(typed))
        new_slots = []
        for slot in main_slots:
            if not slot:
                new_slots.append(slot)
                continue
            new_slot = []
            for conn in slot:
                if (
                    conn.connection_type == FLOWS_TOOL_CONNECTION_TYPE
                    and conn.dest_node_id == consumer_id
                    and src == tool_node_id
                ):
                    new_slot.append(
                        NodeConnection(
                            dest_node_id=executor_id,
                            connection_type=FLOWS_TOOL_CONNECTION_TYPE,
                            index=conn.index,
                        )
                    )
                    rewired = True
                else:
                    new_slot.append(conn)
            new_slots.append(new_slot)
        new_connections[src] = {"main": new_slots}

    if not rewired:
        raise FlowValidationError(f"Could not rewire tool node {ad.flows.node_name(tool_node)}")

    return new_nodes, new_connections, executor_id
