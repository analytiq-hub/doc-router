"""Tests for bulk Run Flows analyze API."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.docrouter_flows.bulk_analyze import (
    batch_flow_result_stored_versions,
    bulk_analyze_flow_executions,
    discover_event_flows_for_tag,
    flow_pair_needs_run,
    get_active_flow_trigger_info,
)
from analytiq_data.docrouter_flows.flow_results import FLOW_RESULTS_COLLECTION
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers
from tests.flows.test_docrouter_flow_results import (
    CODE_NODE_ID,
    TRIGGER_NODE_ID,
    _code_node,
    _create_and_activate_event_flow,
    _event_trigger_node,
    _insert_document,
    _insert_org_tag,
)

TRIGGER_NODE_ID_2 = "dt2"


async def _insert_named_document(
    test_db,
    *,
    name: str,
    tag_ids: list[str] | None = None,
    metadata: dict | None = None,
) -> str:
    document_id = str(ObjectId())
    file_key = f"{document_id}.pdf"
    aq_client = ad.common.get_analytiq_client()
    await ad.common.save_file_async(
        aq_client,
        file_key,
        b"%PDF-1.4 test",
        metadata={"type": "application/pdf"},
    )
    await test_db.docs.insert_one(
        {
            "_id": ObjectId(document_id),
            "organization_id": TEST_ORG_ID,
            "document_id": document_id,
            "user_file_name": name,
            "mongo_file_name": file_key,
            "pdf_file_name": file_key,
            "upload_date": datetime.now(UTC),
            "uploaded_by": "test@example.com",
            "state": ad.common.doc.DOCUMENT_STATE_UPLOADED,
            "tag_ids": tag_ids if tag_ids is not None else [],
            "metadata": metadata if metadata is not None else {},
        }
    )
    return document_id


async def _create_and_activate_custom_flow(
    test_db,
    *,
    nodes: list[dict],
    connections: dict,
) -> tuple[str, str]:
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "custom doc event flow"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "custom doc event flow",
            "nodes": nodes,
            "connections": connections,
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    rev_id = r1.json()["revision"]["flow_revid"]
    r2 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/activate",
        json={},
        headers=get_auth_headers(),
    )
    assert r2.status_code == 200, r2.text
    return flow_id, rev_id


async def _create_and_activate_event_flow_typed(
    test_db,
    *,
    tag_ids: list[str],
    event_type: str = "document.uploaded",
    report_result: bool = True,
) -> tuple[str, str, list[str]]:
    flow_id, rev_id = await _create_and_activate_custom_flow(
        test_db,
        nodes=[
            _event_trigger_node(
                event_type=event_type,
                tag_ids=tag_ids,
                report_result=report_result,
            ),
            _code_node(),
        ],
        connections={
            TRIGGER_NODE_ID: {
                "main": [[{"dest_node_id": CODE_NODE_ID, "connection_type": "main", "index": 0}]],
            },
        },
    )
    return flow_id, rev_id, tag_ids


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


@pytest.mark.asyncio
async def test_bulk_analyze_flows_excludes_report_result_disabled(test_db, mock_auth, setup_test_models):
    tag_id = await _insert_org_tag(test_db, "no-capture-tag")
    flow_id, _, flow_tags = await _create_and_activate_event_flow(
        test_db, report_result=False, tag_ids=[tag_id], auto_tag=False
    )
    await _insert_document(test_db, tag_ids=flow_tags)
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "all",
        flow_ids=[flow_id],
    )
    assert result["total_executions"] == 0


@pytest.mark.asyncio
async def test_bulk_analyze_flows_excludes_non_matching_document_tags(test_db, mock_auth, setup_test_models):
    flow_tag = await _insert_org_tag(test_db, "flow-tag")
    other_tag = await _insert_org_tag(test_db, "other-tag")
    flow_id, _, _ = await _create_and_activate_event_flow(
        test_db, report_result=True, tag_ids=[flow_tag], auto_tag=False
    )
    await _insert_document(test_db, tag_ids=[other_tag])
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "missing",
        flow_ids=[flow_id],
    )
    assert result["total_executions"] == 0


@pytest.mark.asyncio
async def test_bulk_analyze_flows_respects_name_search_filter(test_db, mock_auth, setup_test_models):
    tag_id = await _insert_org_tag(test_db, "name-filter-tag")
    flow_id, _, flow_tags = await _create_and_activate_event_flow(
        test_db, report_result=True, tag_ids=[tag_id], auto_tag=False
    )
    match_id = await _insert_named_document(test_db, name="surgery_packet.pdf", tag_ids=flow_tags)
    await _insert_named_document(test_db, name="invoice.pdf", tag_ids=flow_tags)
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "missing",
        flow_ids=[flow_id],
        name_search="surgery",
    )
    doc_ids = {e["document_id"] for g in result["groups"] for e in g["executions"]}
    assert doc_ids == {match_id}


@pytest.mark.asyncio
async def test_bulk_analyze_flows_respects_metadata_search_filter(test_db, mock_auth, setup_test_models):
    tag_id = await _insert_org_tag(test_db, "meta-filter-tag")
    flow_id, _, flow_tags = await _create_and_activate_event_flow(
        test_db, report_result=True, tag_ids=[tag_id], auto_tag=False
    )
    match_id = await _insert_named_document(
        test_db,
        name="meta_match.pdf",
        tag_ids=flow_tags,
        metadata={"batch": "alpha"},
    )
    await _insert_named_document(
        test_db,
        name="meta_other.pdf",
        tag_ids=flow_tags,
        metadata={"batch": "beta"},
    )
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "missing",
        flow_ids=[flow_id],
        metadata_search={"batch": "alpha"},
    )
    doc_ids = {e["document_id"] for g in result["groups"] for e in g["executions"]}
    assert doc_ids == {match_id}


@pytest.mark.asyncio
async def test_bulk_analyze_flows_flow_ids_only(test_db, mock_auth, setup_test_models):
    tag_id = await _insert_org_tag(test_db, "explicit-flow-tag")
    flow_id, _, flow_tags = await _create_and_activate_event_flow(
        test_db, report_result=True, tag_ids=[tag_id], auto_tag=False
    )
    doc_id, _ = await _insert_document(test_db, tag_ids=flow_tags)
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "missing",
        flow_ids=[flow_id],
    )
    assert result["total_executions"] == 1
    assert result["groups"][0]["flow_id"] == flow_id
    assert {e["document_id"] for e in result["groups"][0]["executions"]} == {doc_id}


@pytest.mark.asyncio
async def test_bulk_analyze_flows_tag_id_only_discovers_via_flow_triggers(test_db, mock_auth, setup_test_models):
    tag_id = await _insert_org_tag(test_db, "discover-tag")
    flow_id, _, flow_tags = await _create_and_activate_event_flow(
        test_db, report_result=True, tag_ids=[tag_id], auto_tag=False
    )
    doc_id, _ = await _insert_document(test_db, tag_ids=flow_tags)
    db = ad.common.get_async_db()
    discovered = await discover_event_flows_for_tag(db, TEST_ORG_ID, tag_id)
    assert flow_id in discovered

    aq = ad.common.get_analytiq_client()
    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "missing",
        tag_id=tag_id,
    )
    assert result["total_executions"] == 1
    assert result["groups"][0]["flow_id"] == flow_id
    assert {e["document_id"] for e in result["groups"][0]["executions"]} == {doc_id}


@pytest.mark.asyncio
async def test_bulk_analyze_flows_intersection_includes_matching_flow(test_db, mock_auth, setup_test_models):
    tag_id = await _insert_org_tag(test_db, "intersect-tag")
    flow_id, _, flow_tags = await _create_and_activate_event_flow(
        test_db, report_result=True, tag_ids=[tag_id], auto_tag=False
    )
    doc_id, _ = await _insert_document(test_db, tag_ids=flow_tags)
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "missing",
        tag_id=tag_id,
        flow_ids=[flow_id],
    )
    assert result["total_executions"] == 1
    assert {e["document_id"] for g in result["groups"] for e in g["executions"]} == {doc_id}


@pytest.mark.asyncio
async def test_bulk_analyze_flows_includes_llm_completed_without_llm_run(test_db, mock_auth, setup_test_models):
    tag_id = await _insert_org_tag(test_db, "llm-flow-tag")
    flow_id, _, flow_tags = await _create_and_activate_event_flow_typed(
        test_db,
        tag_ids=[tag_id],
        event_type="llm.completed",
        report_result=True,
    )
    doc_id, _ = await _insert_document(test_db, tag_ids=flow_tags)
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "missing",
        flow_ids=[flow_id],
    )
    assert result["total_executions"] == 1
    group = result["groups"][0]
    assert group["event_type"] == "llm.completed"
    assert {e["document_id"] for e in group["executions"]} == {doc_id}


@pytest.mark.asyncio
async def test_bulk_analyze_flows_uses_first_matching_trigger_node(test_db, mock_auth, setup_test_models):
    tag_a = await _insert_org_tag(test_db, "trigger-a")
    tag_b = await _insert_org_tag(test_db, "trigger-b")
    flow_id, _ = await _create_and_activate_custom_flow(
        test_db,
        nodes=[
            _event_trigger_node(
                event_type="document.uploaded",
                tag_ids=[tag_a],
                report_result=True,
            ),
            {
                **_event_trigger_node(
                    event_type="document.uploaded",
                    tag_ids=[tag_b],
                    report_result=True,
                ),
                "id": TRIGGER_NODE_ID_2,
                "name": "Doc event B",
            },
            _code_node(),
        ],
        connections={
            TRIGGER_NODE_ID_2: {
                "main": [[{"dest_node_id": CODE_NODE_ID, "connection_type": "main", "index": 0}]],
            },
        },
    )
    doc_id, _ = await _insert_document(test_db, tag_ids=[tag_b])
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "missing",
        flow_ids=[flow_id],
    )
    assert result["total_executions"] == 1
    assert {e["document_id"] for g in result["groups"] for e in g["executions"]} == {doc_id}


@pytest.mark.asyncio
async def test_bulk_analyze_flows_many_documents_batch(test_db, mock_auth, setup_test_models):
    tag_id = await _insert_org_tag(test_db, "batch-tag")
    flow_id, _, flow_tags = await _create_and_activate_event_flow(
        test_db, report_result=True, tag_ids=[tag_id], auto_tag=False
    )
    doc_ids = []
    for i in range(8):
        doc_id, _ = await _insert_document(test_db, tag_ids=flow_tags)
        doc_ids.append(doc_id)
    aq = ad.common.get_analytiq_client()

    result = await bulk_analyze_flow_executions(
        aq,
        TEST_ORG_ID,
        "missing",
        flow_ids=[flow_id],
    )
    assert result["total_executions"] == len(doc_ids)
    found = {e["document_id"] for g in result["groups"] for e in g["executions"]}
    assert found == set(doc_ids)


@pytest.mark.asyncio
async def test_batch_flow_result_stored_versions(test_db, mock_auth, setup_test_models):
    rev_v1 = ObjectId()
    rev_v2 = ObjectId()
    flow_id = str(ObjectId())
    await test_db.flow_revisions.insert_many([
        {"_id": rev_v1, "flow_id": flow_id, "flow_version": 1, "organization_id": TEST_ORG_ID},
        {"_id": rev_v2, "flow_id": flow_id, "flow_version": 2, "organization_id": TEST_ORG_ID},
    ])
    exec_old = ObjectId()
    exec_new = ObjectId()
    await test_db.flow_executions.insert_many([
        {"_id": exec_old, "flow_id": flow_id, "flow_revid": str(rev_v1)},
        {"_id": exec_new, "flow_id": flow_id, "flow_revid": str(rev_v2)},
    ])
    db = ad.common.get_async_db()

    versions = await batch_flow_result_stored_versions(
        db,
        [str(exec_old), str(exec_new), "not-an-object-id"],
    )
    assert versions == {str(exec_old): 1, str(exec_new): 2}


@pytest.mark.asyncio
async def test_get_active_flow_trigger_info(test_db, mock_auth, setup_test_models):
    tag_id = await _insert_org_tag(test_db, "info-tag")
    flow_id, rev_id, _ = await _create_and_activate_event_flow_typed(
        test_db,
        tag_ids=[tag_id],
        event_type="document.uploaded",
    )
    db = ad.common.get_async_db()
    info = await get_active_flow_trigger_info(db, TEST_ORG_ID, flow_id)
    assert info is not None
    assert info.flow_id == flow_id
    assert info.active_version >= 1
    assert info.event_type == "document.uploaded"
    assert str(info.revision["_id"]) == rev_id


@pytest.mark.asyncio
async def test_bulk_analyze_flows_http_happy_path(test_db, mock_auth, setup_test_models):
    tag_id = await _insert_org_tag(test_db, "http-tag")
    flow_id, _, flow_tags = await _create_and_activate_event_flow(
        test_db, report_result=True, tag_ids=[tag_id], auto_tag=False
    )
    doc_id, _ = await _insert_document(test_db, tag_ids=flow_tags)

    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/bulk-analyze",
        json={
            "mode": "missing",
            "tag_id": tag_id,
            "flow_ids": [flow_id],
            "document_filters": {},
        },
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_executions"] == 1
    assert body["groups"][0]["flow_id"] == flow_id
    assert body["groups"][0]["executions"][0]["document_id"] == doc_id
    assert body["groups"][0]["executions"][0]["reason"] == "missing"
