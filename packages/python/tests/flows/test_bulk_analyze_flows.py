"""Tests for bulk Run Flows analyze API."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.docrouter_flows.bulk_analyze import (
    bulk_analyze_flow_executions,
    flow_pair_needs_run,
)
from analytiq_data.docrouter_flows.flow_results import FLOW_RESULTS_COLLECTION
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers
from tests.flows.test_docrouter_flow_results import (
    TRIGGER_NODE_ID,
    _code_node,
    _create_and_activate_event_flow,
    _event_trigger_node,
    _insert_document,
    _insert_org_tag,
)


@pytest.mark.parametrize(
    "mode,has_result,stored,active,expected,reason",
    [
        ("all", False, None, 2, True, "forced"),
        ("missing", False, None, 2, True, "missing"),
        ("missing", True, 1, 2, False, None),
        ("outdated", False, None, 2, True, "missing"),
        ("outdated", True, 1, 2, True, "outdated"),
        ("outdated", True, 2, 2, False, None),
        ("outdated", True, None, 2, True, "outdated"),
    ],
)
def test_flow_pair_needs_run(mode, has_result, stored, active, expected, reason):
    include, got_reason = flow_pair_needs_run(
        mode,
        has_result=has_result,
        stored_version=stored,
        active_version=active,
    )
    assert include is expected
    assert got_reason == reason


async def _bump_flow_to_v2(flow_id: str, tag_ids: list[str]) -> str:
    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    base_revid = r.json()["latest_revision"]["flow_revid"]
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": base_revid,
            "name": "doc event flow",
            "nodes": [
                _event_trigger_node(tag_ids=tag_ids),
                _code_node(python_code=(
                    "def run(items, context):\n"
                    "  out = []\n"
                    "  for it in items:\n"
                    "    j = dict(it.get('json') or {})\n"
                    "    j['flow_output'] = 'v2'\n"
                    "    out.append(j)\n"
                    "  return out\n"
                )),
            ],
            "connections": {
                TRIGGER_NODE_ID: {
                    "main": [[{"dest_node_id": "c1", "connection_type": "main", "index": 0}]],
                },
            },
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    rev_v2 = r1.json()["revision"]["flow_revid"]
    r2 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/activate",
        json={},
        headers=get_auth_headers(),
    )
    assert r2.status_code == 200, r2.text
    return rev_v2


async def _seed_bulk_flow_fixtures(test_db):
    tag_id = await _insert_org_tag(test_db, "bulk-flow-tag")
    flow_id, rev_v1, flow_tags = await _create_and_activate_event_flow(
        test_db, report_result=True, tag_ids=[tag_id], auto_tag=False
    )

    doc_missing, _ = await _insert_document(test_db, tag_ids=flow_tags)
    doc_outdated, _ = await _insert_document(test_db, tag_ids=flow_tags)
    doc_current, _ = await _insert_document(test_db, tag_ids=flow_tags)

    now = datetime.now(UTC)
    exec_outdated = ObjectId()
    exec_current = ObjectId()

    await test_db.flow_executions.insert_many([
        {
            "_id": exec_outdated,
            "organization_id": TEST_ORG_ID,
            "flow_id": flow_id,
            "flow_revid": rev_v1,
            "status": "success",
            "mode": "event",
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": exec_current,
            "organization_id": TEST_ORG_ID,
            "flow_id": flow_id,
            "flow_revid": rev_v1,
            "status": "success",
            "mode": "event",
            "created_at": now,
            "updated_at": now,
        },
    ])

    await test_db[FLOW_RESULTS_COLLECTION].insert_many([
        {
            "org_id": TEST_ORG_ID,
            "document_id": doc_outdated,
            "flow_id": flow_id,
            "execution_id": str(exec_outdated),
            "result": {"flow_output": True},
            "created_at": now,
            "updated_at": now,
        },
        {
            "org_id": TEST_ORG_ID,
            "document_id": doc_current,
            "flow_id": flow_id,
            "execution_id": str(exec_current),
            "result": {"flow_output": True},
            "created_at": now,
            "updated_at": now,
        },
    ])

    rev_v2 = await _bump_flow_to_v2(flow_id, flow_tags)

    await test_db.flow_executions.update_one(
        {"_id": exec_current},
        {"$set": {"flow_revid": rev_v2}},
    )

    return {
        "tag_id": tag_id,
        "flow_id": flow_id,
        "doc_missing": doc_missing,
        "doc_outdated": doc_outdated,
        "doc_current": doc_current,
    }


@pytest.mark.asyncio
async def test_bulk_analyze_flows_missing_mode(test_db, mock_auth, setup_test_models):
    fixtures = await _seed_bulk_flow_fixtures(test_db)
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "missing",
        tag_id=fixtures["tag_id"],
    )

    doc_ids = {e["document_id"] for g in result["groups"] for e in g["executions"]}
    assert fixtures["doc_missing"] in doc_ids
    assert fixtures["doc_outdated"] not in doc_ids
    assert fixtures["doc_current"] not in doc_ids


@pytest.mark.asyncio
async def test_bulk_analyze_flows_outdated_mode(test_db, mock_auth, setup_test_models):
    fixtures = await _seed_bulk_flow_fixtures(test_db)
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "outdated",
        tag_id=fixtures["tag_id"],
    )

    doc_ids = {e["document_id"] for g in result["groups"] for e in g["executions"]}
    assert fixtures["doc_missing"] in doc_ids
    assert fixtures["doc_outdated"] in doc_ids
    assert fixtures["doc_current"] not in doc_ids


@pytest.mark.asyncio
async def test_bulk_analyze_flows_all_mode(test_db, mock_auth, setup_test_models):
    fixtures = await _seed_bulk_flow_fixtures(test_db)
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "all",
        flow_ids=[fixtures["flow_id"]],
    )

    doc_ids = {e["document_id"] for g in result["groups"] for e in g["executions"]}
    assert doc_ids == {
        fixtures["doc_missing"],
        fixtures["doc_outdated"],
        fixtures["doc_current"],
    }
    reasons = {e.get("reason") for g in result["groups"] for e in g["executions"]}
    assert reasons == {"forced"}


@pytest.mark.asyncio
async def test_bulk_analyze_flows_requires_discovery_input(test_db, mock_auth, setup_test_models):
    aq = ad.common.get_analytiq_client()
    with pytest.raises(ValueError, match="tag_id or flow_ids is required"):
        await bulk_analyze_flow_executions(aq, TEST_ORG_ID, "missing")


@pytest.mark.asyncio
async def test_bulk_analyze_flows_http_requires_discovery_input(test_db, mock_auth, setup_test_models):
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/bulk-analyze",
        json={"mode": "missing", "document_filters": {}},
        headers=get_auth_headers(),
    )
    assert r.status_code == 400
    assert "tag_id or flow_ids is required" in r.json()["detail"]


@pytest.mark.asyncio
async def test_bulk_analyze_flows_intersection_empty(test_db, mock_auth, setup_test_models):
    tag_a = await _insert_org_tag(test_db, "tag-a")
    tag_b = await _insert_org_tag(test_db, "tag-b")
    flow_id, _, _ = await _create_and_activate_event_flow(
        test_db, report_result=True, tag_ids=[tag_a], auto_tag=False
    )
    await _insert_document(test_db, tag_ids=[tag_a])
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "all",
        tag_id=tag_b,
        flow_ids=[flow_id],
    )
    assert result["total_executions"] == 0


@pytest.mark.asyncio
async def test_bulk_analyze_flows_excludes_inactive(test_db, mock_auth, setup_test_models):
    tag_id = await _insert_org_tag(test_db, "inactive-tag")
    flow_id, _, flow_tags = await _create_and_activate_event_flow(
        test_db, report_result=True, tag_ids=[tag_id], auto_tag=False
    )
    doc_id, _ = await _insert_document(test_db, tag_ids=flow_tags)
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/deactivate",
        json={},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text

    aq = ad.common.get_analytiq_client()
    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "missing",
        tag_id=tag_id,
    )
    assert result["total_executions"] == 0

    doc_ids = {e["document_id"] for g in result["groups"] for e in g["executions"]}
    assert doc_id not in doc_ids
