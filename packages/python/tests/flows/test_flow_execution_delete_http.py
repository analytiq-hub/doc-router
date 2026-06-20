"""HTTP tests for ``DELETE .../executions/{id}``."""

from __future__ import annotations

from datetime import datetime, UTC

import pytest
import pytest_asyncio
from bson import ObjectId

import analytiq_data as ad

from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


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
async def flow_with_execution(mock_auth, test_db):
    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "execution delete test"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "execution delete test",
            "nodes": [_std_manual_node()],
            "connections": {},
            "settings": {},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text
    rev_id = r1.json()["revision"]["flow_revid"]

    exec_oid = ObjectId()
    exec_id = str(exec_oid)
    db = ad.common.get_async_db()
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
    return flow_id, exec_id


@pytest.mark.asyncio
async def test_delete_execution_removes_document(flow_with_execution, mock_auth, test_db):
    flow_id, exec_id = flow_with_execution
    db = ad.common.get_async_db()

    r = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}",
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    assert await db.flow_executions.count_documents({"_id": ObjectId(exec_id)}) == 0


@pytest.mark.asyncio
async def test_delete_execution_removes_flow_blobs(flow_with_execution, mock_auth, test_db):
    flow_id, exec_id = flow_with_execution
    blob_key = f"{exec_id}/n1/0/out.bin"
    aq_client = ad.common.get_analytiq_client()
    await ad.mongodb.blob.save_blob_async(
        aq_client,
        bucket="flow_blobs",
        key=blob_key,
        blob=b"exec-blob-bytes",
        metadata={"mime_type": "application/octet-stream", "file_name": "out.bin"},
    )
    assert await ad.mongodb.blob.get_blob_async(aq_client, "flow_blobs", blob_key) is not None

    r = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}",
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    assert await ad.mongodb.blob.get_blob_async(aq_client, "flow_blobs", blob_key) is None


@pytest.mark.asyncio
async def test_delete_running_execution_rejected(flow_with_execution, mock_auth, test_db):
    flow_id, exec_id = flow_with_execution
    db = ad.common.get_async_db()
    await db.flow_executions.update_one({"_id": ObjectId(exec_id)}, {"$set": {"status": "running"}})

    r = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}",
        headers=get_auth_headers(),
    )
    assert r.status_code == 409, r.text
    assert await db.flow_executions.count_documents({"_id": ObjectId(exec_id)}) == 1
