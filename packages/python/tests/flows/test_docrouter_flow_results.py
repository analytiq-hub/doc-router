"""Tests for DocRouter event-trigger ``report_result`` capture and document flow result APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from bson import ObjectId

import analytiq_data as ad
import analytiq_data.queue.queue as queue_mod
from analytiq_data.docrouter_flows.event_dispatch import dispatch_docrouter_event
from analytiq_data.docrouter_flows.flow_results import FLOW_RESULTS_COLLECTION
from analytiq_data.msg_handlers import process_flow_run_msg
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers

TRIGGER_NODE_ID = "dt1"
CODE_NODE_ID = "c1"


def _event_trigger_node(
    *,
    event_type: str = "document.uploaded",
    tag_ids: list[str] | None = None,
    prompt_id: str = "",
    report_result: bool = True,
) -> dict:
    return {
        "id": TRIGGER_NODE_ID,
        "name": "Doc event",
        "type": "docrouter.trigger",
        "position": [0, 0],
        "parameters": {
            "event_type": event_type,
            "tag_ids": tag_ids if tag_ids is not None else [],
            "prompt_id": prompt_id,
            "report_result": report_result,
        },
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


def _code_node(*, python_code: str | None = None) -> dict:
    code = python_code or (
        "def run(items, context):\n"
        "  out = []\n"
        "  for it in items:\n"
        "    j = dict(it.get('json') or {})\n"
        "    j['flow_output'] = True\n"
        "    out.append(j)\n"
        "  return out\n"
    )
    return {
        "id": CODE_NODE_ID,
        "name": "Code",
        "type": "flows.code",
        "position": [200, 0],
        "parameters": {"python_code": code},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


@pytest.fixture(autouse=True)
def _stop_background_flow_run_worker():
    _orig = queue_mod.recv_msg

    async def _recv_shim(aclient, qname: str):
        if qname == "flow_run":
            return None
        return await _orig(aclient, qname)

    queue_mod.recv_msg = _recv_shim
    yield
    queue_mod.recv_msg = _orig


@pytest.fixture(autouse=True)
def _register_docrouter_nodes():
    ad.flows.register_builtin_nodes()
    ad.flows.register_docrouter_nodes()


async def _insert_document(test_db, *, tag_ids: list[str] | None = None) -> tuple[str, str]:
    document_id = str(ObjectId())
    file_key = f"{document_id}.pdf"
    aq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()
    await ad.common.save_file_async(
        aq_client,
        file_key,
        b"%PDF-1.4 test",
        metadata={"type": "application/pdf"},
    )
    await db.docs.insert_one(
        {
            "_id": ObjectId(document_id),
            "organization_id": TEST_ORG_ID,
            "document_id": document_id,
            "user_file_name": "invoice.pdf",
            "mongo_file_name": file_key,
            "pdf_file_name": file_key,
            "upload_date": datetime.now(UTC),
            "uploaded_by": "test@example.com",
            "state": ad.common.doc.DOCUMENT_STATE_UPLOADED,
            "tag_ids": tag_ids if tag_ids is not None else [],
            "metadata": {"source": "test"},
        }
    )
    return document_id, file_key


async def _insert_org_tag(test_db, name: str) -> str:
    tag_id = ObjectId()
    await test_db.tags.insert_one(
        {
            "_id": tag_id,
            "name": name,
            "color": "#3B82F6",
            "organization_id": TEST_ORG_ID,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )
    return str(tag_id)


async def _create_and_activate_event_flow(
    test_db,
    *,
    report_result: bool = True,
    tag_ids: list[str] | None = None,
    auto_tag: bool = True,
) -> tuple[str, str, list[str]]:
    if tag_ids is None:
        tag_ids = [await _insert_org_tag(test_db, f"trigger-{ObjectId()}")] if auto_tag else []
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "doc event flow"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]
    nodes = [
        _event_trigger_node(report_result=report_result, tag_ids=tag_ids),
        _code_node(),
    ]
    connections = {
        TRIGGER_NODE_ID: {
            "main": [[{"dest_node_id": CODE_NODE_ID, "connection_type": "main", "index": 0}]],
        },
    }
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "doc event flow",
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
    return flow_id, rev_id, tag_ids


async def _run_queued_flow(aq_client, exec_id: str) -> None:
    db = ad.common.get_async_db()
    q0 = await db["queues.flow_run"].find_one({"msg.execution_id": exec_id})
    assert q0 is not None
    with patch.object(queue_mod, "recv_msg", side_effect=lambda _a, qname: q0 if qname == "flow_run" else None):
        await process_flow_run_msg(aq_client, q0)


@pytest.mark.asyncio
async def test_activate_stores_report_result_on_flow_triggers_row(test_db, mock_auth):
    flow_id, _, _ = await _create_and_activate_event_flow(test_db, report_result=False)
    db = ad.common.get_async_db()
    row = await db.flow_triggers.find_one({"flow_id": flow_id, "trigger_node_id": TRIGGER_NODE_ID})
    assert row is not None
    assert row["report_result"] is False


@pytest.mark.asyncio
async def test_flow_run_captures_last_node_result_when_report_result_enabled(test_db, mock_auth):
    flow_id, _, flow_tags = await _create_and_activate_event_flow(test_db, report_result=True)
    document_id, _ = await _insert_document(test_db, tag_ids=flow_tags)
    aq_client = ad.common.get_analytiq_client()

    exec_ids = await dispatch_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        event_type="document.uploaded",
        document_id=document_id,
    )
    assert len(exec_ids) == 1
    await _run_queued_flow(aq_client, exec_ids[0])

    db = ad.common.get_async_db()
    row = await db[FLOW_RESULTS_COLLECTION].find_one({"document_id": document_id, "flow_id": flow_id})
    assert row is not None
    assert row["execution_id"] == exec_ids[0]
    assert row["result"]["flow_output"] is True
    assert row["result"]["document_id"] == document_id


@pytest.mark.asyncio
async def test_flow_run_skips_capture_when_report_result_disabled(test_db, mock_auth):
    flow_id, _, flow_tags = await _create_and_activate_event_flow(test_db, report_result=False)
    document_id, _ = await _insert_document(test_db, tag_ids=flow_tags)
    aq_client = ad.common.get_analytiq_client()

    exec_ids = await dispatch_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        event_type="document.uploaded",
        document_id=document_id,
    )
    assert len(exec_ids) == 1
    await _run_queued_flow(aq_client, exec_ids[0])

    db = ad.common.get_async_db()
    assert await db[FLOW_RESULTS_COLLECTION].count_documents({"document_id": document_id}) == 0


@pytest.mark.asyncio
async def test_flow_result_upsert_overwrites_previous_run(test_db, mock_auth):
    flow_id, _, flow_tags = await _create_and_activate_event_flow(test_db, report_result=True)
    document_id, _ = await _insert_document(test_db, tag_ids=flow_tags)
    aq_client = ad.common.get_analytiq_client()

    exec_ids_1 = await dispatch_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        event_type="document.uploaded",
        document_id=document_id,
    )
    await _run_queued_flow(aq_client, exec_ids_1[0])

    exec_ids_2 = await dispatch_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        event_type="document.uploaded",
        document_id=document_id,
    )
    await _run_queued_flow(aq_client, exec_ids_2[0])

    db = ad.common.get_async_db()
    rows = await db[FLOW_RESULTS_COLLECTION].find({"document_id": document_id}).to_list(length=None)
    assert len(rows) == 1
    assert rows[0]["execution_id"] == exec_ids_2[0]


@pytest.mark.asyncio
async def test_list_flows_for_document_http(test_db, mock_auth):
    flow_id, _, flow_tags = await _create_and_activate_event_flow(test_db, report_result=True)
    document_id, _ = await _insert_document(test_db, tag_ids=flow_tags)
    aq_client = ad.common.get_analytiq_client()

    exec_ids = await dispatch_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        event_type="document.uploaded",
        document_id=document_id,
    )
    await _run_queued_flow(aq_client, exec_ids[0])

    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        params={"document_id": document_id},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["flow"]["flow_id"] == flow_id
    assert item["flow"]["name"] == "doc event flow"
    assert item["has_captured_result"] is True
    assert item["event_type"] == "document.uploaded"


@pytest.mark.asyncio
async def test_get_flow_document_result_http(test_db, mock_auth):
    flow_id, rev_id, flow_tags = await _create_and_activate_event_flow(test_db, report_result=True)
    document_id, _ = await _insert_document(test_db, tag_ids=flow_tags)
    aq_client = ad.common.get_analytiq_client()

    exec_ids = await dispatch_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        event_type="document.uploaded",
        document_id=document_id,
    )
    await _run_queued_flow(aq_client, exec_ids[0])

    r_by_flow = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/result/{document_id}",
        params={"flow_id": flow_id},
        headers=get_auth_headers(),
    )
    assert r_by_flow.status_code == 200, r_by_flow.text
    item = r_by_flow.json()
    assert item["flow_id"] == flow_id
    assert item["flow_name"] == "doc event flow"
    assert item["flow_revid"] == rev_id
    assert item["flow_version"] == 1
    assert item["execution_id"] == exec_ids[0]
    assert item["result"]["flow_output"] is True

    r_by_revid = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/result/{document_id}",
        params={"flow_revid": rev_id},
        headers=get_auth_headers(),
    )
    assert r_by_revid.status_code == 200, r_by_revid.text
    assert r_by_revid.json()["flow_id"] == flow_id


@pytest.mark.asyncio
async def test_get_flow_document_result_not_found_without_capture(test_db, mock_auth):
    flow_id, _, flow_tags = await _create_and_activate_event_flow(test_db, report_result=True)
    document_id, _ = await _insert_document(test_db, tag_ids=flow_tags)

    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/result/{document_id}",
        params={"flow_id": flow_id},
        headers=get_auth_headers(),
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_delete_document_removes_flow_results(test_db, mock_auth):
    flow_id, _, flow_tags = await _create_and_activate_event_flow(test_db, report_result=True)
    document_id, _ = await _insert_document(test_db, tag_ids=flow_tags)
    aq_client = ad.common.get_analytiq_client()

    exec_ids = await dispatch_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        event_type="document.uploaded",
        document_id=document_id,
    )
    await _run_queued_flow(aq_client, exec_ids[0])

    db = ad.common.get_async_db()
    assert await db[FLOW_RESULTS_COLLECTION].count_documents({"document_id": document_id}) == 1

    r = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{document_id}",
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    assert await db[FLOW_RESULTS_COLLECTION].count_documents({"document_id": document_id}) == 0


@pytest.mark.asyncio
async def test_list_flows_for_document_includes_matching_flow_without_result(test_db, mock_auth):
    flow_id, _, flow_tags = await _create_and_activate_event_flow(test_db, report_result=True)
    document_id, _ = await _insert_document(test_db, tag_ids=flow_tags)

    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        params={"document_id": document_id},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["flow"]["flow_id"] == flow_id
    assert item["has_captured_result"] is False


@pytest.mark.asyncio
async def test_list_flows_for_document_respects_trigger_tag_filter(test_db, mock_auth):
    tag_id = str(ObjectId())
    matching_flow_id, _, _ = await _create_and_activate_event_flow(test_db, tag_ids=[tag_id])
    other_flow_id, _, _ = await _create_and_activate_event_flow(test_db, tag_ids=[str(ObjectId())])
    document_id, _ = await _insert_document(test_db, tag_ids=[tag_id])

    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        params={"document_id": document_id},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    flow_ids = {item["flow"]["flow_id"] for item in r.json()["items"]}
    assert matching_flow_id in flow_ids
    assert other_flow_id not in flow_ids
