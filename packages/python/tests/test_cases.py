"""Tests for org-scoped document cases."""

import asyncio
import base64

import pytest
from bson import ObjectId
from datetime import datetime, UTC

import analytiq_data as ad
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers, get_token_headers


async def _insert_doc(test_db, *, case_id=None, organization_id=TEST_ORG_ID, tag_ids=None):
    doc_id = ObjectId()
    doc = {
        "_id": doc_id,
        "organization_id": organization_id,
        "user_file_name": f"{doc_id}.pdf",
        "mongo_file_name": f"{doc_id}.pdf",
        "document_id": str(doc_id),
        "pdf_id": str(doc_id),
        "upload_date": datetime.now(UTC),
        "uploaded_by": "test",
        "state": "uploaded",
        "tag_ids": tag_ids or [],
        "metadata": {},
        "updated_at": datetime.now(UTC),
    }
    if case_id is not None:
        doc["case_id"] = case_id
    await test_db.docs.insert_one(doc)
    return doc_id


def _create_case(case_id, headers=None):
    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        json={"case_id": case_id},
        headers=headers or get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


_PDF_B64 = base64.b64encode(b"%PDF-1.4\n%%EOF\n").decode()


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


@pytest.mark.asyncio
async def test_list_cases_document_counts(test_db, mock_auth):
    _create_case("CNT-1")
    _create_case("CNT-2")
    await _insert_doc(test_db, case_id="CNT-1")
    await _insert_doc(test_db, case_id="CNT-1")

    resp = client.get(f"/v0/orgs/{TEST_ORG_ID}/cases?case_id_search=CNT-", headers=get_auth_headers())
    assert resp.status_code == 200
    counts = {c["case_id"]: c["document_count"] for c in resp.json()["cases"]}
    assert counts == {"CNT-1": 2, "CNT-2": 0}


@pytest.mark.asyncio
async def test_assign_with_create_case_if_missing_and_duplicate_ids(test_db, mock_auth):
    doc_id = await _insert_doc(test_db)
    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases/NEW-1/documents",
        json={"document_ids": [str(doc_id), str(doc_id)], "create_case_if_missing": True},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["count"] == 1
    assert (await test_db.docs.find_one({"_id": doc_id}))["case_id"] == "NEW-1"
    assert await test_db.cases.count_documents({"organization_id": TEST_ORG_ID, "case_id": "NEW-1"}) == 1


@pytest.mark.asyncio
async def test_assign_to_case_being_deleted_returns_409(test_db, mock_auth):
    _create_case("DEL-ING")
    await test_db.cases.update_one(
        {"case_id": "DEL-ING"}, {"$set": {"deleting_at": datetime.now(UTC), "delete_cascade": False}}
    )
    doc_id = await _insert_doc(test_db)
    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases/DEL-ING/documents",
        json={"document_ids": [str(doc_id)]},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_remove_document_from_case_being_deleted_or_missing(test_db, mock_auth):
    _create_case("RM-DEL")
    await test_db.cases.update_one(
        {"case_id": "RM-DEL"}, {"$set": {"deleting_at": datetime.now(UTC), "delete_cascade": False}}
    )
    in_deleting = await _insert_doc(test_db, case_id="RM-DEL")
    orphan = await _insert_doc(test_db, case_id="NO-ROW")

    for doc_id in (in_deleting, orphan):
        resp = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
            json={"case_id": None},
            headers=get_auth_headers(),
        )
        assert resp.status_code == 200, resp.text
        assert (await test_db.docs.find_one({"_id": doc_id})).get("case_id") is None


@pytest.mark.asyncio
async def test_put_document_unknown_case_leaves_other_fields_unchanged(test_db, mock_auth):
    doc_id = await _insert_doc(test_db)
    resp = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
        json={"document_name": "renamed.pdf", "metadata": {"a": "b"}, "case_id": "NO-SUCH"},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 400
    doc = await test_db.docs.find_one({"_id": doc_id})
    assert doc["user_file_name"] != "renamed.pdf"
    assert doc["metadata"] == {}
    assert doc.get("case_id") is None


@pytest.mark.asyncio
async def test_put_document_case_id_omitted_or_assigned(test_db, mock_auth):
    _create_case("PUT-1")
    doc_id = await _insert_doc(test_db, case_id="PUT-1")

    resp = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
        json={"document_name": "renamed.pdf"},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200
    doc = await test_db.docs.find_one({"_id": doc_id})
    assert doc["case_id"] == "PUT-1"
    assert doc["user_file_name"] == "renamed.pdf"

    _create_case("PUT-2")
    resp = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
        json={"case_id": "PUT-2", "metadata": {"k": "v"}},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    doc = await test_db.docs.find_one({"_id": doc_id})
    assert doc["case_id"] == "PUT-2"
    assert doc["metadata"] == {"k": "v"}


@pytest.mark.asyncio
async def test_upload_with_case(test_db, mock_auth):
    _create_case("UP-1")
    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [{"name": "a.pdf", "content": _PDF_B64, "case_id": "UP-1"}]},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    doc_id = resp.json()["documents"][0]["document_id"]
    assert (await test_db.docs.find_one({"_id": ObjectId(doc_id)}))["case_id"] == "UP-1"


@pytest.mark.asyncio
async def test_upload_rejects_bad_case_before_saving_anything(test_db, mock_auth):
    _create_case("UP-2")
    before = await test_db.docs.count_documents({"organization_id": TEST_ORG_ID})
    for bad_case_id in ("NO-SUCH", "", "bad id!"):
        resp = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/documents",
            json={
                "documents": [
                    {"name": "a.pdf", "content": _PDF_B64, "case_id": "UP-2"},
                    {"name": "b.pdf", "content": _PDF_B64, "case_id": bad_case_id},
                ]
            },
            headers=get_auth_headers(),
        )
        assert resp.status_code == 400, (bad_case_id, resp.text)
    assert await test_db.docs.count_documents({"organization_id": TEST_ORG_ID}) == before


@pytest.mark.asyncio
async def test_delete_case_resumes_after_interruption(test_db, mock_auth):
    _create_case("RES-1")
    doc_id = await _insert_doc(test_db, case_id="RES-1")
    # Simulate a delete that set deleting_at and then stopped.
    await test_db.cases.update_one(
        {"case_id": "RES-1"}, {"$set": {"deleting_at": datetime.now(UTC), "delete_cascade": False}}
    )

    resp = client.delete(f"/v0/orgs/{TEST_ORG_ID}/cases/RES-1?cascade=true", headers=get_auth_headers())
    assert resp.status_code == 409

    resp = client.delete(f"/v0/orgs/{TEST_ORG_ID}/cases/RES-1", headers=get_auth_headers())
    assert resp.status_code == 200, resp.text
    assert (await test_db.docs.find_one({"_id": doc_id})).get("case_id") is None
    assert await test_db.cases.count_documents({"case_id": "RES-1"}) == 0

    resp = client.delete(f"/v0/orgs/{TEST_ORG_ID}/cases/RES-1", headers=get_auth_headers())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cascade_delete_requires_org_admin(test_db, org_and_users):
    org_id = org_and_users["org_id"]
    member = org_and_users["member"]
    admin = org_and_users["admin"]

    resp = client.post(
        f"/v0/orgs/{org_id}/cases", json={"case_id": "CAS-1"}, headers=get_token_headers(admin["token"])
    )
    assert resp.status_code == 200, resp.text
    kept = await _insert_doc(test_db, organization_id=org_id)
    member_doc = await _insert_doc(test_db, organization_id=org_id, case_id="CAS-1")

    resp = client.delete(f"/v0/orgs/{org_id}/cases/CAS-1?cascade=true", headers=get_token_headers(member["token"]))
    assert resp.status_code == 403

    resp = client.delete(f"/v0/orgs/{org_id}/cases/CAS-1?cascade=true", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 202, resp.text
    # TestClient runs background tasks before returning.
    assert await test_db.docs.find_one({"_id": member_doc}) is None
    assert await test_db.docs.find_one({"_id": kept}) is not None
    assert await test_db.cases.count_documents({"organization_id": org_id, "case_id": "CAS-1"}) == 0


@pytest.mark.asyncio
async def test_concurrent_assign_and_delete_leave_no_orphans(test_db, mock_auth):
    analytiq_client = ad.common.get_analytiq_client()
    for i in range(10):
        case_id = f"RACE-{i}"
        _create_case(case_id)
        doc_ids = [str(await _insert_doc(test_db)) for _ in range(3)]

        async def assign(doc_id):
            try:
                await ad.common.assign_documents_to_case(
                    analytiq_client, TEST_ORG_ID, [doc_id], case_id,
                    create_case_if_missing=False, created_by="test",
                )
            except LookupError:
                pass

        await asyncio.gather(
            *(assign(d) for d in doc_ids),
            ad.common.delete_case(analytiq_client, TEST_ORG_ID, case_id, cascade_documents=False),
        )
        assert await test_db.cases.count_documents({"case_id": case_id}) == 0
        assert await test_db.docs.count_documents({"case_id": case_id}) == 0


@pytest.mark.asyncio
async def test_delete_document_removes_related_data(test_db, mock_auth):
    doc_id = await _insert_doc(test_db)
    did = str(doc_id)
    scope = {"organization_id": TEST_ORG_ID, "document_id": did}
    await test_db.form_submissions.insert_one({**scope, "form_revid": "x"})
    await test_db.chat_threads.insert_one({**scope, "created_by": "u", "messages": []})
    await test_db.webhook_deliveries.insert_one({**scope, "status": "pending"})
    finished = await test_db.flow_executions.insert_one(
        {"organization_id": TEST_ORG_ID, "flow_id": "f", "status": "success", "trigger": {"document_id": did}}
    )
    running = await test_db.flow_executions.insert_one(
        {"organization_id": TEST_ORG_ID, "flow_id": "f2", "status": "running", "trigger": {"document_id": did}}
    )

    resp = client.delete(f"/v0/orgs/{TEST_ORG_ID}/documents/{did}", headers=get_auth_headers())
    assert resp.status_code == 200, resp.text

    assert await test_db.docs.find_one({"_id": doc_id}) is None
    for coll in ("form_submissions", "chat_threads", "webhook_deliveries"):
        assert await test_db[coll].count_documents(scope) == 0, coll
    assert await test_db.flow_executions.find_one({"_id": finished.inserted_id}) is None
    running_doc = await test_db.flow_executions.find_one({"_id": running.inserted_id})
    assert running_doc["stop_requested"] is True


@pytest.mark.asyncio
async def test_delete_doc_without_docs_row_still_cleans_up(test_db, mock_auth):
    did = str(ObjectId())
    scope = {"organization_id": TEST_ORG_ID, "document_id": did}
    await test_db.form_submissions.insert_one({**scope, "form_revid": "x"})
    await ad.common.delete_doc(ad.common.get_analytiq_client(), did, TEST_ORG_ID)
    assert await test_db.form_submissions.count_documents(scope) == 0


@pytest.mark.parametrize("case_id", [".", "..", "..."])
def test_validate_case_id_rejects_dot_only_ids(case_id):
    with pytest.raises(ValueError):
        ad.common.validate_case_id(case_id)
    assert ad.common.validate_case_id("a.b") == "a.b"
