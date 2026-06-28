"""Find flows that reference another flow via Flow Tool / Execute Flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

_TARGET_NODE_TYPES = frozenset({"flows.flow_tool", "flows.execute_flow"})


@dataclass(frozen=True, slots=True)
class FlowTargetReference:
    flow_id: str
    flow_name: str
    node_id: str
    node_name: str
    node_type: str


def _node_references_target(node: dict[str, Any], target_flow_id: str) -> bool:
    if node.get("type") not in _TARGET_NODE_TYPES:
        return False
    params = node.get("parameters")
    if not isinstance(params, dict):
        return False
    return str(params.get("target_flow_id") or "").strip() == target_flow_id


def _reference_from_node(hdr: dict[str, Any], node: dict[str, Any]) -> FlowTargetReference:
    fid = str(hdr["_id"])
    return FlowTargetReference(
        flow_id=fid,
        flow_name=str(hdr.get("name") or fid),
        node_id=str(node.get("id") or ""),
        node_name=str(node.get("name") or node.get("type") or "node"),
        node_type=str(node.get("type") or ""),
    )


async def find_flows_referencing_target(
    db: Any,
    *,
    organization_id: str,
    target_flow_id: str,
) -> list[FlowTargetReference]:
    """Return org flows whose latest saved revision references ``target_flow_id``."""

    target = target_flow_id.strip()
    if not target:
        return []

    hdr_filter: dict[str, Any] = {"organization_id": organization_id}
    try:
        hdr_filter["_id"] = {"$ne": ObjectId(target)}
    except InvalidId:
        pass

    headers = await db.flows.find(hdr_filter, {"_id": 1, "name": 1}).to_list(None)
    refs: list[FlowTargetReference] = []
    for hdr in headers:
        parent_flow_id = str(hdr["_id"])
        latest = await db.flow_revisions.find_one(
            {"flow_id": parent_flow_id},
            sort=[("flow_version", -1)],
            projection={"nodes": 1},
        )
        if not latest:
            continue
        nodes = latest.get("nodes")
        if not isinstance(nodes, list):
            continue
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if _node_references_target(node, target):
                refs.append(_reference_from_node(hdr, node))
                break
    refs.sort(key=lambda r: r.flow_name.lower())
    return refs


def format_flow_delete_blocked_message(refs: list[FlowTargetReference]) -> str:
    if not refs:
        return "Cannot delete this flow: it is referenced by another flow."
    if len(refs) == 1:
        r = refs[0]
        kind = "Flow Tool" if r.node_type == "flows.flow_tool" else "Execute Flow"
        return (
            f'Cannot delete this flow: it is referenced by "{r.flow_name}" '
            f'({kind} node "{r.node_name}"). Remove or retarget that node first.'
        )
    shown = refs[:5]
    names = ", ".join(f'"{r.flow_name}"' for r in shown)
    suffix = f" and {len(refs) - len(shown)} more" if len(refs) > len(shown) else ""
    return (
        f"Cannot delete this flow: it is referenced by {len(refs)} other flow(s): "
        f"{names}{suffix}. Remove or retarget those nodes first."
    )
