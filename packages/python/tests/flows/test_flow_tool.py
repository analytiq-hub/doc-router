"""Flow Tool (callable sub-flow) dispatch tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.flows.agent_loop.dispatch import execute_tool_call
from analytiq_data.flows.agent_loop.types import NormalizedToolCall
from analytiq_data.flows.tool_wiring import WiredTool
from tests.conftest_utils import TEST_ORG_ID, TEST_USER_ID


def _std_node(id_: str, ntype: str, x: int = 0, parameters: dict | None = None) -> dict:
    return {
        "id": id_,
        "name": id_,
        "type": ntype,
        "position": [x, 0],
        "parameters": parameters or {},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


def _callable_subflow_revision() -> tuple[list[dict], dict]:
    nodes = [
        _std_node("tt", "flows.trigger.tool", 0),
        _std_node(
            "code",
            "flows.code",
            200,
            {
                "mode": "all_items",
                "python_code": "def run(items, context):\n  return items\n",
            },
        ),
    ]
    connections = {
        "tt": {"main": [[{"dest_node_id": "code", "connection_type": "main", "index": 0}]]},
    }
    return nodes, connections


async def _seed_callable_flow(
    db,
    *,
    active: bool = True,
    callable_as_tool: bool = True,
) -> tuple[str, str]:
    flow_id = ObjectId()
    rev_id = ObjectId()
    now = datetime.now(UTC)
    nodes, connections = _callable_subflow_revision()

    await db.flows.insert_one(
        {
            "_id": flow_id,
            "organization_id": TEST_ORG_ID,
            "name": "Callable sub-flow",
            "active": active,
            "active_flow_revid": str(rev_id) if active else None,
            "callable_as_tool": callable_as_tool,
            "flow_version": 1,
            "created_at": now,
            "created_by": TEST_USER_ID,
            "updated_at": now,
            "updated_by": TEST_USER_ID,
        }
    )
    await db.flow_revisions.insert_one(
        {
            "_id": rev_id,
            "flow_id": str(flow_id),
            "flow_version": 1,
            "nodes": nodes,
            "connections": connections,
            "settings": {},
            "pin_data": None,
            "created_at": now,
            "created_by": TEST_USER_ID,
        }
    )
    return str(flow_id), str(rev_id)


def _wired_flow_tool(*, target_flow_id: str) -> WiredTool:
    return WiredTool(
        name="run_subflow",
        description="Run sub-flow",
        parameters_schema={"type": "object", "properties": {"value": {"type": "string"}}},
        node_id="ft-1",
        node_type="flows.flow_tool",
        node={
            "id": "ft-1",
            "parameters": {
                "tool_name": "run_subflow",
                "tool_description": "Run sub-flow",
                "target_flow_id": target_flow_id,
            },
        },
    )


@pytest.fixture(autouse=True)
def _register_nodes() -> None:
    ad.flows.register_builtin_nodes()
    ad.flows.register_docrouter_nodes()


@pytest.fixture
def parent_ctx(test_db) -> ad.flows.ExecutionContext:
    aclient = ad.common.get_analytiq_client()
    return ad.flows.ExecutionContext(
        organization_id=TEST_ORG_ID,
        execution_id=str(ObjectId()),
        flow_id=str(ObjectId()),
        flow_revid=str(ObjectId()),
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=aclient,
        flow_id_stack=[],
    )


@pytest.mark.asyncio
async def test_flow_tool_dispatch_runs_callable_subflow(test_db, parent_ctx: ad.flows.ExecutionContext) -> None:
    target_flow_id, _ = await _seed_callable_flow(test_db)
    wired = _wired_flow_tool(target_flow_id=target_flow_id)
    tc = NormalizedToolCall(id="1", name="run_subflow", arguments={"value": "passed-through"})

    raw = await execute_tool_call(
        tc,
        wired,
        parent_ctx,
        consumer_node_id="agent-1",
        parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
    )

    payload = json.loads(raw)
    assert payload.get("value") == "passed-through"


@pytest.mark.asyncio
async def test_flow_tool_rejects_cycle(test_db, parent_ctx: ad.flows.ExecutionContext) -> None:
    target_flow_id, _ = await _seed_callable_flow(test_db)
    parent_ctx.flow_id_stack = [target_flow_id, parent_ctx.flow_id]
    wired = _wired_flow_tool(target_flow_id=target_flow_id)
    tc = NormalizedToolCall(id="1", name="run_subflow", arguments={})

    raw = await execute_tool_call(
        tc,
        wired,
        parent_ctx,
        consumer_node_id="agent-1",
        parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
    )

    assert json.loads(raw) == {"error": "Sub-flow cycle detected"}


@pytest.mark.asyncio
async def test_flow_tool_rejects_inactive_target(test_db, parent_ctx: ad.flows.ExecutionContext) -> None:
    target_flow_id, _ = await _seed_callable_flow(test_db, active=False)
    wired = _wired_flow_tool(target_flow_id=target_flow_id)
    tc = NormalizedToolCall(id="1", name="run_subflow", arguments={})

    raw = await execute_tool_call(
        tc,
        wired,
        parent_ctx,
        consumer_node_id="agent-1",
        parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
    )

    assert json.loads(raw) == {"error": "Target flow is not active"}


@pytest.mark.asyncio
async def test_flow_tool_rejects_non_callable_target(test_db, parent_ctx: ad.flows.ExecutionContext) -> None:
    target_flow_id, _ = await _seed_callable_flow(test_db, callable_as_tool=False)
    wired = _wired_flow_tool(target_flow_id=target_flow_id)
    tc = NormalizedToolCall(id="1", name="run_subflow", arguments={})

    raw = await execute_tool_call(
        tc,
        wired,
        parent_ctx,
        consumer_node_id="agent-1",
        parent_item=ad.flows.FlowItem(json={}, binary={}, meta={}),
    )

    assert json.loads(raw) == {"error": "Target flow is not callable as a tool"}
