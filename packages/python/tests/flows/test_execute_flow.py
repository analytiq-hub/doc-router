"""Execute Flow node integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from bson import ObjectId

import analytiq_data as ad
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


async def _seed_subflow(db, *, output_key: str = "result") -> str:
    flow_id = ObjectId()
    rev_id = ObjectId()
    now = datetime.now(UTC)
    nodes = [
        _std_node("tt", "flows.trigger.tool", 0),
        _std_node(
            "code",
            "flows.code",
            200,
            {
                "mode": "all_items",
                "python_code": (
                    "def run(items, context):\n"
                    "  val = (items[0].get('json') or {}).get('value', 'ok')\n"
                    f"  return [{{'{output_key}': val}}]\n"
                ),
            },
        ),
    ]
    connections = {
        "tt": {"main": [[{"dest_node_id": "code", "connection_type": "main", "index": 0}]]},
    }

    await db.flows.insert_one(
        {
            "_id": flow_id,
            "organization_id": TEST_ORG_ID,
            "name": "Child sub-flow",
            "active": True,
            "active_flow_revid": str(rev_id),
            "callable_as_tool": False,
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
    return str(flow_id)


@pytest.fixture(autouse=True)
def _register_nodes() -> None:
    ad.flows.register_builtin_nodes()
    ad.flows.register_docrouter_nodes()


@pytest.mark.asyncio
async def test_execute_flow_node_returns_last_node_output(test_db) -> None:
    child_flow_id = await _seed_subflow(test_db)
    aclient = ad.common.get_analytiq_client()

    parent_nodes = [
        _std_node("m", "flows.trigger.manual", 0),
        _std_node(
            "prep",
            "flows.code",
            100,
            {
                "mode": "all_items",
                "python_code": "def run(items, context):\n  return [{'value': 'hello-subflow'}]\n",
            },
        ),
        _std_node(
            "ef",
            "flows.execute_flow",
            200,
            {"target_flow_id": child_flow_id, "mode": "each"},
        ),
    ]
    parent_connections = {
        "m": {"main": [[{"dest_node_id": "prep", "connection_type": "main", "index": 0}]]},
        "prep": {"main": [[{"dest_node_id": "ef", "connection_type": "main", "index": 0}]]},
    }
    revision = {
        "nodes": parent_nodes,
        "connections": parent_connections,
        "settings": {},
        "pin_data": None,
    }

    ctx = ad.flows.ExecutionContext(
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

    await ad.flows.run_flow(context=ctx, revision=revision, start_trigger_node_id="m")

    ef_run = ctx.run_data.get("ef") or {}
    assert ef_run.get("status") == "success"
    main = ef_run.get("data", {}).get("main")
    assert isinstance(main, list) and main and main[0]
    out_json = main[0][0].json if hasattr(main[0][0], "json") else main[0][0].get("json")
    assert out_json.get("result") == "hello-subflow"
