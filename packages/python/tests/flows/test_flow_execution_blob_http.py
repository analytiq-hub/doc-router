"""HTTP tests for execution-scoped binary download (`GET .../executions/{id}/blob`)."""

from __future__ import annotations

from datetime import datetime, UTC
from io import BytesIO

import pytest
import pytest_asyncio
from bson import ObjectId

import analytiq_data as ad

import app.routes.flows as flows_routes
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
        json={"name": "execution blob test"},
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]
    r1 = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={
            "base_flow_revid": "",
            "name": "execution blob test",
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
    return flow_id, rev_id, exec_id


def test_parse_binary_storage_id_rejects_malformed() -> None:
    with pytest.raises(Exception) as exc:
        flows_routes._parse_binary_storage_id("no-colon")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_execution_blob_unknown_bucket_rejected(flow_with_execution, mock_auth, test_db):
    flow_id, _rev_id, exec_id = flow_with_execution
    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}/blob",
        params={"storage_id": "unknown_bucket:some/key", "action": "download"},
        headers=get_auth_headers(),
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_execution_blob_flow_blobs_roundtrip(flow_with_execution, mock_auth, test_db):
    flow_id, _rev_id, exec_id = flow_with_execution
    payload = b"exec-blob-bytes"
    key = f"{exec_id}/n1/0/pdf"
    aq_client = ad.common.get_analytiq_client()
    await ad.mongodb.blob.save_blob_async(
        aq_client,
        bucket="flow_blobs",
        key=key,
        blob=payload,
        metadata={"mime_type": "application/pdf", "file_name": "doc.pdf"},
    )

    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}/blob",
        params={"storage_id": f"flow_blobs:{key}", "action": "download"},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    assert r.content == payload
    assert "application/pdf" in r.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_execution_blob_flow_blobs_wrong_execution_forbidden(flow_with_execution, mock_auth, test_db):
    flow_id, _rev_id, exec_id = flow_with_execution
    other_exec = str(ObjectId())
    key = f"{other_exec}/n1/0/pdf"
    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}/blob",
        params={"storage_id": f"flow_blobs:{key}", "action": "download"},
        headers=get_auth_headers(),
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_execution_blob_files_roundtrip(flow_with_execution, mock_auth, test_db):
    flow_id, _rev_id, exec_id = flow_with_execution
    document_id = str(ObjectId())
    file_key = f"{document_id}.pdf"
    payload = b"%PDF-1.4 flow files bucket"
    aq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()

    await ad.common.save_file_async(
        aq_client,
        file_key,
        payload,
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
            "tag_ids": [],
            "metadata": {},
        }
    )

    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}/blob",
        params={"storage_id": f"files:{file_key}", "action": "download"},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    assert r.content == payload
    assert 'filename="invoice.pdf"' in r.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_execution_blob_files_wrong_org_not_found(flow_with_execution, mock_auth, test_db):
    flow_id, _rev_id, exec_id = flow_with_execution
    other_org = str(ObjectId())
    document_id = str(ObjectId())
    file_key = f"{document_id}.pdf"
    aq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db()

    await ad.common.save_file_async(aq_client, file_key, b"x", metadata={"type": "application/pdf"})
    await db.docs.insert_one(
        {
            "_id": ObjectId(document_id),
            "organization_id": other_org,
            "document_id": document_id,
            "user_file_name": "secret.pdf",
            "mongo_file_name": file_key,
            "pdf_file_name": file_key,
            "upload_date": datetime.now(UTC),
            "uploaded_by": "other@example.com",
            "state": ad.common.doc.DOCUMENT_STATE_UPLOADED,
            "tag_ids": [],
            "metadata": {},
        }
    )

    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}/blob",
        params={"storage_id": f"files:{file_key}", "action": "download"},
        headers=get_auth_headers(),
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_execution_blob_flow_pins_roundtrip(flow_with_execution, mock_auth, test_db):
    flow_id, rev_id, exec_id = flow_with_execution
    payload = b"pinned-in-execution-view"
    files = {"file": ("pin.bin", BytesIO(payload), "application/octet-stream")}
    data = {"node_id": "n1", "slot": "0", "item_index": "0", "property": "data"}
    r_up = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/revisions/{rev_id}/pins/binary",
        data=data,
        files=files,
        headers={"Authorization": "Bearer test_token"},
    )
    assert r_up.status_code == 200, r_up.text
    storage_id = r_up.json()["storage_id"]

    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}/blob",
        params={"storage_id": storage_id, "action": "download"},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    assert r.content == payload


@pytest.mark.asyncio
async def test_execution_blob_flow_pins_wrong_revision_forbidden(flow_with_execution, mock_auth, test_db):
    flow_id, rev_id, exec_id = flow_with_execution
    files = {"file": ("pin.bin", BytesIO(b"x"), "application/octet-stream")}
    data = {"node_id": "n1", "slot": "0", "item_index": "0", "property": "data"}
    r_up = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/revisions/{rev_id}/pins/binary",
        data=data,
        files=files,
        headers={"Authorization": "Bearer test_token"},
    )
    assert r_up.status_code == 200, r_up.text
    storage_id = r_up.json()["storage_id"]

    other_rev = str(ObjectId())
    db = ad.common.get_async_db()
    await db.flow_executions.update_one(
        {"_id": ObjectId(exec_id)},
        {"$set": {"flow_revid": other_rev}},
    )

    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/executions/{exec_id}/blob",
        params={"storage_id": storage_id, "action": "download"},
        headers=get_auth_headers(),
    )
    assert r.status_code in (403, 404), r.text
