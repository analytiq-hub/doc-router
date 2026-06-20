"""HTTP tests for full flow delete cleanup (revisions, executions, blobs, triggers)."""

from __future__ import annotations

from datetime import datetime, UTC
from io import BytesIO

import pytest
import pytest_asyncio
from bson import ObjectId

import analytiq_data as ad

from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


def _auth_multipart_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test_token"}


def _std_manual_node() -> dict:
    return {
        "id": "t1",
        "name": "Start",
        "type": "flows.trigger.manual",
        "position": [0, 0],
        "parameters": {},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


@pytest_asyncio.fixture
async def flow_with_associated_data(mock_auth, test_db):
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "flow delete cleanup test"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "flow delete cleanup test",
            "nodes": [_std_manual_node()],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    rev_id = r1.json()["revision"]["flow_revid"]

    files = {"file": ("blob.bin", BytesIO(b"pin-bytes"), "application/octet-stream")}
    data = {"node_id": "n1", "slot": "0", "item_index": "0", "property": "data"}
    r_up = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/revisions/{rev_id}/pins/binary",
        data=data,
        files=files,
        headers=_auth_multipart_headers(),
    )
    assert r_up.status_code == 200, r_up.text
    pin_key = r_up.json()["storage_id"].split(":", 1)[1]

    db = ad.common.get_async_db()
    exec_oid = ObjectId()
    exec_id = str(exec_oid)
    await db.flow_executions.insert_one(
        {
            "_id": exec_oid,
            "flow_id": flow_id,
            "flow_revid": rev_id,
            "organization_id": TEST_ORG_ID,
            "mode": "manual",
            "status": "success",
            "started_at": datetime.now(UTC),
            "finished_at": datetime.now(UTC),
            "run_data": {},
            "trigger": {},
            "start_trigger_node_id": "t1",
        }
    )

    aq_client = ad.common.get_analytiq_client()
    exec_blob_key = f"{exec_id}/node/out.bin"
    await ad.mongodb.blob.save_blob_async(
        aq_client,
        bucket="flow_blobs",
        key=exec_blob_key,
        blob=b"exec-blob",
        metadata={"mime_type": "application/octet-stream", "file_name": "out.bin"},
    )

    await db.flow_triggers.insert_one(
        {
            "flow_id": flow_id,
            "org_id": TEST_ORG_ID,
            "trigger_node_id": "t1",
            "trigger_type": "document.uploaded",
            "flow_revid": rev_id,
        }
    )
    await db.flow_trigger_registrations.insert_one(
        {
            "flow_id": flow_id,
            "organization_id": TEST_ORG_ID,
            "node_id": "t1",
            "rule_index": 0,
            "trigger_kind": "schedule",
        }
    )
    await db.flow_static_data.insert_one(
        {"flow_id": flow_id, "node_id": "t1", "data": {"cursor": "x"}, "created_at": datetime.now(UTC)}
    )
    await db.flow_trigger_leases.insert_one(
        {
            "_id": f"{flow_id}:t1:2026-01-01T00:00",
            "flow_id": flow_id,
            "node_id": "t1",
            "tick_key": "2026-01-01T00:00",
            "expires_at": datetime.now(UTC),
            "created_at": datetime.now(UTC),
        }
    )
    await db.flow_webhook_routes.insert_one(
        {
            "_id": "cleanup-test-leaf",
            "leaf": "cleanup-test-leaf",
            "production": {"flow_id": flow_id, "organization_id": TEST_ORG_ID},
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )

    return flow_id, rev_id, exec_id, pin_key, exec_blob_key


@pytest.mark.asyncio
async def test_delete_flow_removes_all_associated_data(flow_with_associated_data, mock_auth, test_db):
    flow_id, rev_id, exec_id, pin_key, exec_blob_key = flow_with_associated_data
    db = ad.common.get_async_db()
    aq_client = ad.common.get_analytiq_client()

    assert await ad.mongodb.blob.get_blob_async(aq_client, "flow_pins", pin_key) is not None
    assert await ad.mongodb.blob.get_blob_async(aq_client, "flow_blobs", exec_blob_key) is not None

    r = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}

    assert await db.flows.count_documents({"_id": ObjectId(flow_id)}) == 0
    assert await db.flow_revisions.count_documents({"flow_id": flow_id}) == 0
    assert await db.flow_executions.count_documents({"flow_id": flow_id}) == 0
    assert await db.flow_triggers.count_documents({"flow_id": flow_id}) == 0
    assert await db.flow_trigger_registrations.count_documents({"flow_id": flow_id}) == 0
    assert await db.flow_static_data.count_documents({"flow_id": flow_id}) == 0
    assert await db.flow_trigger_leases.count_documents({"flow_id": flow_id}) == 0
    assert await db.flow_webhook_routes.count_documents({"_id": "cleanup-test-leaf"}) == 0

    assert await ad.mongodb.blob.get_blob_async(aq_client, "flow_pins", pin_key) is None
    assert await ad.mongodb.blob.get_blob_async(aq_client, "flow_blobs", exec_blob_key) is None

    r_get = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}",
        headers=get_auth_headers(),
    )
    assert r_get.status_code == 404
