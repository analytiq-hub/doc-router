"""Tests for org-scoped document cases."""

import pytest
from bson import ObjectId
from datetime import datetime, UTC

from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


@pytest.mark.asyncio
async def test_create_and_get_case(test_db, mock_auth):
    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        json={
            "case_id": "CLM-100",
            "display_name": "Test claim",
            "metadata": {"claim_date": "2026-01-01"},
        },
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == "CLM-100"
    assert body["document_count"] == 0

    resp2 = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/cases/CLM-100",
        headers=get_auth_headers(),
    )
    assert resp2.status_code == 200
    assert resp2.json()["display_name"] == "Test claim"


@pytest.mark.asyncio
async def test_duplicate_case_returns_409(test_db, mock_auth):
    client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        json={"case_id": "CLM-dup"},
        headers=get_auth_headers(),
    )
    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        json={"case_id": "CLM-dup"},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_assign_document_to_case(test_db, mock_auth):
    client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        json={"case_id": "CLM-200"},
        headers=get_auth_headers(),
    )
    doc_id = ObjectId()
    await test_db.docs.insert_one(
        {
            "_id": doc_id,
            "organization_id": TEST_ORG_ID,
            "user_file_name": "a.pdf",
            "mongo_file_name": "f.pdf",
            "document_id": str(doc_id),
            "pdf_id": str(doc_id),
            "upload_date": datetime.now(UTC),
            "uploaded_by": "test",
            "state": "uploaded",
            "tag_ids": [],
            "metadata": {},
            "updated_at": datetime.now(UTC),
        }
    )

    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases/CLM-200/documents",
        json={"document_ids": [str(doc_id)]},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200

    doc = await test_db.docs.find_one({"_id": doc_id})
    assert doc["case_id"] == "CLM-200"

    resp_list = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents?case_id=CLM-200",
        headers=get_auth_headers(),
    )
    assert resp_list.status_code == 200
    assert resp_list.json()["total_count"] == 1


@pytest.mark.asyncio
async def test_assign_unknown_case_without_create_fails(test_db, mock_auth):
    doc_id = ObjectId()
    await test_db.docs.insert_one(
        {
            "_id": doc_id,
            "organization_id": TEST_ORG_ID,
            "user_file_name": "b.pdf",
            "mongo_file_name": "g.pdf",
            "document_id": str(doc_id),
            "pdf_id": str(doc_id),
            "upload_date": datetime.now(UTC),
            "uploaded_by": "test",
            "state": "uploaded",
            "tag_ids": [],
            "metadata": {},
            "updated_at": datetime.now(UTC),
        }
    )
    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases/NO-SUCH/documents",
        json={"document_ids": [str(doc_id)]},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_put_document_case_id_null_removes(test_db, mock_auth):
    client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        json={"case_id": "CLM-300"},
        headers=get_auth_headers(),
    )
    doc_id = ObjectId()
    await test_db.docs.insert_one(
        {
            "_id": doc_id,
            "organization_id": TEST_ORG_ID,
            "user_file_name": "c.pdf",
            "mongo_file_name": "h.pdf",
            "document_id": str(doc_id),
            "pdf_id": str(doc_id),
            "upload_date": datetime.now(UTC),
            "uploaded_by": "test",
            "state": "uploaded",
            "tag_ids": [],
            "metadata": {},
            "case_id": "CLM-300",
            "updated_at": datetime.now(UTC),
        }
    )

    resp = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
        json={"case_id": None},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200
    doc = await test_db.docs.find_one({"_id": doc_id})
    assert doc.get("case_id") is None


@pytest.mark.asyncio
async def test_delete_case_clears_document_case_id(test_db, mock_auth):
    client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        json={"case_id": "CLM-400"},
        headers=get_auth_headers(),
    )
    doc_id = ObjectId()
    await test_db.docs.insert_one(
        {
            "_id": doc_id,
            "organization_id": TEST_ORG_ID,
            "user_file_name": "d.pdf",
            "mongo_file_name": "i.pdf",
            "document_id": str(doc_id),
            "pdf_id": str(doc_id),
            "upload_date": datetime.now(UTC),
            "uploaded_by": "test",
            "state": "uploaded",
            "tag_ids": [],
            "metadata": {},
            "case_id": "CLM-400",
            "updated_at": datetime.now(UTC),
        }
    )

    resp = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/cases/CLM-400",
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200
    doc = await test_db.docs.find_one({"_id": doc_id})
    assert doc.get("case_id") is None
    assert await test_db.cases.count_documents({"case_id": "CLM-400"}) == 0
