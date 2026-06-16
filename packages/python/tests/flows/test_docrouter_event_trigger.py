"""Tests for ``docrouter.trigger`` event dispatch and activation."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from bson import ObjectId

import analytiq_data as ad
import analytiq_data.queue.queue as queue_mod
from analytiq_data.docrouter_flows.event_dispatch import (
    _evaluate_trigger_row,
    dispatch_docrouter_event,
)
from analytiq_data.msg_handlers import process_flow_run_msg
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers

TRIGGER_NODE_ID = "dt1"
CODE_NODE_ID = "c1"


def _event_trigger_node(
    *,
    event_type: str = "document.uploaded",
    tag_id: str = "",
    prompt_id: str = "",
) -> dict:
    return {
        "id": TRIGGER_NODE_ID,
        "name": "Doc event",
        "type": "docrouter.trigger",
        "position": [0, 0],
        "parameters": {
            "event_type": event_type,
            "tag_id": tag_id,
            "prompt_id": prompt_id,
        },
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


def _code_node() -> dict:
    return {
        "id": CODE_NODE_ID,
        "name": "Code",
        "type": "flows.code",
        "position": [200, 0],
        "parameters": {"language": "python", "code": "return _items"},
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
            "tag_ids": tag_ids or [],
            "metadata": {"source": "test"},
        }
    )
    return document_id, file_key


async def _create_and_activate_event_flow(
    test_db,
    *,
    event_type: str = "document.uploaded",
    tag_id: str = "",
    prompt_id: str = "",
    with_code_downstream: bool = True,
) -> tuple[str, str]:
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "doc event flow"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]
    nodes = [_event_trigger_node(
        event_type=event_type,
        tag_id=tag_id,
        prompt_id=prompt_id,
    )]
    connections: dict = {}
    if with_code_downstream:
        nodes.append(_code_node())
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
    return flow_id, rev_id


def test_evaluate_trigger_row_tag_filter() -> None:
    row = {"tag_id": "tag-a"}
    doc = {"tag_ids": ["tag-b"]}
    matches, _ = _evaluate_trigger_row(
        row, event_type="document.uploaded", doc=doc, prompt_id=None
    )
    assert matches is False

    doc2 = {"tag_ids": ["tag-a"]}
    matches2, matched = _evaluate_trigger_row(
        row, event_type="document.uploaded", doc=doc2, prompt_id=None
    )
    assert matches2 is True
    assert matched == "tag-a"


def test_evaluate_trigger_row_prompt_filter() -> None:
    row = {"tag_id": "", "prompt_id": "prompt-a"}
    doc = {"tag_ids": []}
    matches, _ = _evaluate_trigger_row(
        row, event_type="llm.completed", doc=doc, prompt_id="prompt-b"
    )
    assert matches is False

    matches2, _ = _evaluate_trigger_row(
        row, event_type="llm.completed", doc=doc, prompt_id="prompt-a"
    )
    assert matches2 is True

    matches3, _ = _evaluate_trigger_row(
        row, event_type="llm.error", doc=doc, prompt_id="prompt-a"
    )
    assert matches3 is True


@pytest.mark.asyncio
async def test_activate_registers_flow_triggers_row(test_db, mock_auth):
    flow_id, rev_id = await _create_and_activate_event_flow(test_db)
    db = ad.common.get_async_db()
    row = await db.flow_triggers.find_one({"flow_id": flow_id, "trigger_node_id": TRIGGER_NODE_ID})
    assert row is not None
    assert row["trigger_type"] == "document.uploaded"
    assert row["org_id"] == TEST_ORG_ID
    assert row["flow_revid"] == rev_id


@pytest.mark.asyncio
async def test_deactivate_removes_flow_triggers_row(test_db, mock_auth):
    flow_id, _ = await _create_and_activate_event_flow(test_db)
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/deactivate",
        json={},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    db = ad.common.get_async_db()
    assert await db.flow_triggers.count_documents({"flow_id": flow_id}) == 0


@pytest.mark.asyncio
async def test_dispatch_document_uploaded_enqueues_flow_run(test_db, mock_auth):
    flow_id, _ = await _create_and_activate_event_flow(test_db)
    document_id, _ = await _insert_document(test_db)
    aq_client = ad.common.get_analytiq_client()

    exec_ids = await dispatch_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        event_type="document.uploaded",
        document_id=document_id,
    )
    assert len(exec_ids) == 1

    db = ad.common.get_async_db()
    exec_doc = await db.flow_executions.find_one({"_id": ObjectId(exec_ids[0])})
    assert exec_doc is not None
    assert exec_doc["flow_id"] == flow_id
    assert exec_doc["mode"] == "event"
    trigger = exec_doc["trigger"]
    assert trigger["document_id"] == document_id
    assert trigger["event_type"] == "document.uploaded"
    assert trigger["type"] == "docrouter.event"
    assert trigger["items"][0][0]["json"]["document_id"] == document_id
    assert trigger["items"][0][0]["binary"]["pdf"]["storage_id"].startswith("files:")


@pytest.mark.asyncio
async def test_dispatch_skips_when_tag_filter_mismatch(test_db, mock_auth):
    await _create_and_activate_event_flow(test_db, tag_id="wanted-tag")
    document_id, _ = await _insert_document(test_db, tag_ids=["other-tag"])
    aq_client = ad.common.get_analytiq_client()
    exec_ids = await dispatch_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        event_type="document.uploaded",
        document_id=document_id,
    )
    assert exec_ids == []


@pytest.mark.asyncio
async def test_dispatch_llm_completed_prompt_id_filter(test_db, mock_auth):
    await _create_and_activate_event_flow(test_db, event_type="llm.completed", prompt_id="prompt-a")
    document_id, _ = await _insert_document(test_db)
    aq_client = ad.common.get_analytiq_client()

    assert (
        await dispatch_docrouter_event(
            aq_client,
            organization_id=TEST_ORG_ID,
            event_type="llm.completed",
            document_id=document_id,
            prompt_id="prompt-b",
            trigger_llm_result={"ok": True},
        )
        == []
    )

    exec_ids = await dispatch_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        event_type="llm.completed",
        document_id=document_id,
        prompt_id="prompt-a",
        prompt_revid="rev-prompt-a",
        llm_run_id="6a31799ec5729d2678e16ecc",
        trigger_llm_result={"ok": True},
    )
    assert len(exec_ids) == 1

    db = ad.common.get_async_db()
    exec_doc = await db.flow_executions.find_one({"_id": ObjectId(exec_ids[0])})
    assert exec_doc is not None
    assert exec_doc["trigger"]["event_type"] == "llm.completed"
    assert exec_doc["trigger"]["prompt_id"] == "prompt-a"
    assert exec_doc["trigger"]["prompt_revid"] == "rev-prompt-a"
    assert exec_doc["trigger"]["llm_run_id"] == "6a31799ec5729d2678e16ecc"
    assert "prompt_name" not in exec_doc["trigger"]
    item_json = exec_doc["trigger"]["items"][0][0]["json"]
    assert item_json["llm_run_id"] == "6a31799ec5729d2678e16ecc"
    assert item_json["prompt_id"] == "prompt-a"
    assert item_json["prompt_revid"] == "rev-prompt-a"
    assert "prompt_name" not in item_json


@pytest.mark.asyncio
async def test_dispatch_llm_error_prompt_id_filter(test_db, mock_auth):
    await _create_and_activate_event_flow(test_db, event_type="llm.error", prompt_id="prompt-a")
    document_id, _ = await _insert_document(test_db)
    aq_client = ad.common.get_analytiq_client()

    assert (
        await dispatch_docrouter_event(
            aq_client,
            organization_id=TEST_ORG_ID,
            event_type="llm.error",
            document_id=document_id,
            prompt_id="prompt-b",
            error_message="boom",
            error_code="llm",
        )
        == []
    )

    exec_ids = await dispatch_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        event_type="llm.error",
        document_id=document_id,
        prompt_id="prompt-a",
        prompt_revid="rev-prompt-a",
        error_message="boom",
        error_code="llm",
    )
    assert len(exec_ids) == 1

    db = ad.common.get_async_db()
    exec_doc = await db.flow_executions.find_one({"_id": ObjectId(exec_ids[0])})
    assert exec_doc is not None
    assert exec_doc["trigger"]["event_type"] == "llm.error"
    assert exec_doc["trigger"]["prompt_id"] == "prompt-a"
    assert exec_doc["trigger"]["prompt_revid"] == "rev-prompt-a"
    assert exec_doc["trigger"]["error_message"] == "boom"


@pytest.mark.asyncio
async def test_event_trigger_node_replays_trigger_items(test_db, mock_auth):
    await _create_and_activate_event_flow(test_db, with_code_downstream=False)
    document_id, _ = await _insert_document(test_db)
    aq_client = ad.common.get_analytiq_client()
    exec_ids = await dispatch_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        event_type="document.uploaded",
        document_id=document_id,
    )
    assert len(exec_ids) == 1
    exec_id = exec_ids[0]

    db = ad.common.get_async_db()
    q0 = await db["queues.flow_run"].find_one({"msg.execution_id": exec_id})
    assert q0 is not None

    with patch.object(queue_mod, "recv_msg", side_effect=lambda _a, qname: q0 if qname == "flow_run" else None):
        await process_flow_run_msg(aq_client, q0)

    exec_doc = await db.flow_executions.find_one({"_id": ObjectId(exec_id)})
    assert exec_doc["status"] == "success", exec_doc.get("error")
    run_data = exec_doc.get("run_data") or {}
    trig_out = run_data.get(TRIGGER_NODE_ID, {}).get("data", {}).get("main", [[]])[0]
    assert trig_out[0]["json"]["document_id"] == document_id
    assert trig_out[0]["json"]["file_name"] == "invoice.pdf"


@pytest.mark.asyncio
async def test_save_active_flow_updates_flow_triggers(test_db, mock_auth):
    flow_id, rev_id_r1 = await _create_and_activate_event_flow(test_db, tag_id="")
    db = ad.common.get_async_db()
    row_before = await db.flow_triggers.find_one({"flow_id": flow_id, "trigger_node_id": TRIGGER_NODE_ID})
    assert row_before is not None
    assert row_before["flow_revid"] == rev_id_r1
    assert row_before["tag_id"] == ""

    r_save = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": rev_id_r1,
            "name": "doc event flow",
            "nodes": [_event_trigger_node(event_type="llm.completed", tag_id="new-tag-on-draft")],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r_save.status_code == 200, r_save.text
    rev_id_r2 = r_save.json()["revision"]["flow_revid"]
    assert rev_id_r2 != rev_id_r1

    row_after = await db.flow_triggers.find_one({"flow_id": flow_id, "trigger_node_id": TRIGGER_NODE_ID})
    assert row_after is not None
    assert row_after["flow_revid"] == rev_id_r2
    assert row_after["trigger_type"] == "llm.completed"
    assert row_after["tag_id"] == "new-tag-on-draft"

    hdr = await db.flows.find_one({"_id": ObjectId(flow_id)})
    assert hdr is not None
    assert hdr.get("active_flow_revid") == rev_id_r2


@pytest.mark.asyncio
async def test_save_rejects_invalid_docrouter_trigger_event_type(test_db, mock_auth):
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "bad trigger flow"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]
    bad_node = _event_trigger_node()
    bad_node["parameters"] = {"event_type": "not.a.real.event"}
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "bad trigger flow",
            "nodes": [bad_node],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 400, r1.text


@pytest.mark.asyncio
async def test_notify_llm_completed_docrouter_event_dispatches(test_db, mock_auth):
    await _create_and_activate_event_flow(test_db, event_type="llm.completed", prompt_id="prompt-a")
    document_id, _ = await _insert_document(test_db)
    aq_client = ad.common.get_analytiq_client()
    prompt_revid = str(ObjectId())

    await test_db.prompt_revisions.insert_one(
        {
            "_id": ObjectId(prompt_revid),
            "prompt_id": "prompt-a",
            "prompt_version": 1,
            "organization_id": TEST_ORG_ID,
        }
    )
    llm_run_id = str(
        (
            await test_db.llm_runs.insert_one(
                {
                    "document_id": document_id,
                    "prompt_revid": prompt_revid,
                    "prompt_id": "prompt-a",
                    "prompt_version": 1,
                    "llm_result": {"field": "value"},
                }
            )
        ).inserted_id
    )

    exec_ids = await ad.llm.notify_llm_completed_docrouter_event(
        aq_client,
        organization_id=TEST_ORG_ID,
        document_id=document_id,
        prompt_revid=prompt_revid,
        llm_result={"field": "value"},
        llm_run_id=llm_run_id,
    )
    assert len(exec_ids) == 1


@pytest.mark.asyncio
async def test_run_llm_skips_dispatch_on_cache_hit(test_db, mock_auth, monkeypatch):
    document_id, _ = await _insert_document(test_db)
    aq_client = ad.common.get_analytiq_client()
    notify_calls: list[dict] = []

    async def track_notify(*_args, **kwargs):
        notify_calls.append(kwargs)
        return []

    async def fake_get_llm_result(*_args, **_kwargs):
        return {"llm_result": {"cached": True}}

    monkeypatch.setattr("analytiq_data.llm.llm.notify_llm_completed_docrouter_event", track_notify)
    monkeypatch.setattr("analytiq_data.llm.llm.get_llm_result", fake_get_llm_result)

    result = await ad.llm.run_llm(
        aq_client,
        document_id=document_id,
        prompt_revid="default",
        force=False,
    )
    assert result == {"cached": True}
    assert notify_calls == []
