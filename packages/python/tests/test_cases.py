"""Tests for org-scoped document cases."""

import asyncio
import base64
import json

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
async def test_delete_document_in_case_leaves_case_intact(test_db, mock_auth):
    """Deleting a member document removes the doc but not the case row (plan §2.3)."""
    _create_case("DOC-IN-CASE")
    doc_id = await _insert_doc(test_db, case_id="DOC-IN-CASE")
    did = str(doc_id)

    resp = client.delete(f"/v0/orgs/{TEST_ORG_ID}/documents/{did}", headers=get_auth_headers())
    assert resp.status_code == 200, resp.text
    assert await test_db.docs.find_one({"_id": doc_id}) is None
    assert await test_db.cases.count_documents({"case_id": "DOC-IN-CASE"}) == 1

    listed = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/cases/DOC-IN-CASE",
        headers=get_auth_headers(),
    )
    assert listed.status_code == 200
    assert listed.json()["document_count"] == 0


@pytest.mark.asyncio
async def test_list_cases_api_updated_after_and_sort(test_db, mock_auth):
    await test_db["cases"].insert_many(
        [
            {
                "organization_id": TEST_ORG_ID,
                "case_id": "API-OLD",
                "display_name": "Old",
                "tag_ids": [],
                "metadata": {},
                "created_by": "u1",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            },
            {
                "organization_id": TEST_ORG_ID,
                "case_id": "API-NEW",
                "display_name": "New",
                "tag_ids": [],
                "metadata": {},
                "created_by": "u1",
                "created_at": datetime(2026, 3, 1, tzinfo=UTC),
                "updated_at": datetime(2026, 3, 1, tzinfo=UTC),
            },
        ]
    )
    resp = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        params={"updated_after": "2026-02-01T00:00:00Z", "limit": 50},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    ids = {c["case_id"] for c in resp.json()["cases"]}
    assert ids == {"API-NEW"}

    sort = json.dumps([{"field": "case_id", "sort": "asc"}])
    resp = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        params={"sort": sort, "limit": 50},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    assert [c["case_id"] for c in resp.json()["cases"] if c["case_id"].startswith("API-")] == [
        "API-NEW",
        "API-OLD",
    ]


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


@pytest.mark.asyncio
async def test_list_cases_search_matches_display_name(test_db, mock_auth):
    await ad.common.create_case(
        ad.common.get_analytiq_client(),
        TEST_ORG_ID,
        case_id="CLM-NAME-1",
        display_name="Smith auto loss",
        tag_ids=[],
        metadata={},
        created_by="u1",
    )
    await ad.common.create_case(
        ad.common.get_analytiq_client(),
        TEST_ORG_ID,
        case_id="CLM-OTHER",
        display_name="Other",
        tag_ids=[],
        metadata={},
        created_by="u1",
    )
    cases, total = await ad.common.list_cases(
        ad.common.get_analytiq_client(),
        TEST_ORG_ID,
        case_id_search="smith auto",
    )
    assert total == 1
    assert cases[0]["case_id"] == "CLM-NAME-1"


@pytest.mark.asyncio
async def test_list_cases_grid_created_at_date_range(test_db, mock_auth):
    """Created column filters: day bucket (is) and onOrAfter/onOrBefore range."""
    coll = test_db["cases"]
    await coll.insert_many(
        [
            {
                "organization_id": TEST_ORG_ID,
                "case_id": "CASE-EARLY",
                "display_name": "Early",
                "tag_ids": [],
                "metadata": {},
                "created_by": "u1",
                "created_at": datetime(2026, 1, 10, 12, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 10, 12, 0, tzinfo=UTC),
            },
            {
                "organization_id": TEST_ORG_ID,
                "case_id": "CASE-MID",
                "display_name": "Mid",
                "tag_ids": [],
                "metadata": {},
                "created_by": "u1",
                "created_at": datetime(2026, 2, 15, 8, 30, tzinfo=UTC),
                "updated_at": datetime(2026, 2, 15, 8, 30, tzinfo=UTC),
            },
            {
                "organization_id": TEST_ORG_ID,
                "case_id": "CASE-LATE",
                "display_name": "Late",
                "tag_ids": [],
                "metadata": {},
                "created_by": "u1",
                "created_at": datetime(2026, 3, 20, 23, 59, tzinfo=UTC),
                "updated_at": datetime(2026, 3, 20, 23, 59, tzinfo=UTC),
            },
        ]
    )

    filters = json.dumps(
        {
            "items": [
                {"field": "created_at", "operator": "is", "value": "2026-02-15T00:00:00.000Z"},
            ],
            "logicOperator": "and",
        }
    )
    resp = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        params={"filters": filters, "limit": 50},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    ids = {c["case_id"] for c in resp.json()["cases"]}
    assert ids == {"CASE-MID"}

    filters = json.dumps(
        {
            "items": [
                {"field": "created_at", "operator": "onOrAfter", "value": "2026-02-01T00:00:00.000Z"},
                {"field": "created_at", "operator": "onOrBefore", "value": "2026-02-28T00:00:00.000Z"},
            ],
            "logicOperator": "and",
        }
    )
    resp = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        params={"filters": filters, "limit": 50},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    ids = {c["case_id"] for c in resp.json()["cases"]}
    assert ids == {"CASE-MID"}


@pytest.mark.parametrize("case_id", [".", "..", "..."])
def test_validate_case_id_rejects_dot_only_ids(case_id):
    with pytest.raises(ValueError):
        ad.common.validate_case_id(case_id)
    assert ad.common.validate_case_id("a.b") == "a.b"


@pytest.mark.asyncio
async def test_list_cases_default_sort_is_updated_at_desc(test_db, mock_auth):
    """With no sort model, cases come back most recently updated first (not by case id)."""
    await test_db["cases"].insert_many(
        [
            {
                "organization_id": TEST_ORG_ID,
                "case_id": case_id,
                "display_name": case_id,
                "tag_ids": [],
                "metadata": {},
                "created_by": "u1",
                "created_at": updated,
                "updated_at": updated,
            }
            for case_id, updated in [
                ("CASE-Z-OLD", datetime(2026, 1, 1, tzinfo=UTC)),
                ("CASE-A-NEW", datetime(2026, 3, 1, tzinfo=UTC)),
                ("CASE-M-MID", datetime(2026, 2, 1, tzinfo=UTC)),
            ]
        ]
    )
    aq = ad.common.get_analytiq_client()
    cases, _ = await ad.common.list_cases(aq, TEST_ORG_ID)
    assert [c["case_id"] for c in cases] == ["CASE-A-NEW", "CASE-M-MID", "CASE-Z-OLD"]

    # An explicit sort by case_id alone is still honored.
    cases, _ = await ad.common.list_cases(
        aq, TEST_ORG_ID, sort_model=[{"field": "case_id", "sort": "asc"}]
    )
    assert [c["case_id"] for c in cases] == ["CASE-A-NEW", "CASE-M-MID", "CASE-Z-OLD"]
    cases, _ = await ad.common.list_cases(
        aq, TEST_ORG_ID, sort_model=[{"field": "case_id", "sort": "desc"}]
    )
    assert [c["case_id"] for c in cases] == ["CASE-Z-OLD", "CASE-M-MID", "CASE-A-NEW"]


async def _insert_prompt(test_db, *, name="Case prompt"):
    prompt_id = ObjectId()
    await test_db.prompts.insert_one(
        {
            "_id": prompt_id,
            "organization_id": TEST_ORG_ID,
            "name": name,
        }
    )
    rev_id = ObjectId()
    await test_db.prompt_revisions.insert_one(
        {
            "_id": rev_id,
            "prompt_id": str(prompt_id),
            "prompt_version": 1,
            "content": "Extract fields.",
            "organization_id": TEST_ORG_ID,
            "tag_ids": [],
            "model": "gpt-4o-mini",
            "include": {"ocr_text": False, "pdf": False, "metadata_keys": []},
            "created_at": datetime.now(UTC),
            "created_by": "test",
        }
    )
    return str(prompt_id), str(rev_id)


@pytest.mark.asyncio
async def test_case_llm_run_rejects_prompt_without_shared_tag(test_db, mock_auth):
    tag_id = ObjectId()
    await test_db.tags.insert_one(
        {
            "_id": tag_id,
            "organization_id": TEST_ORG_ID,
            "name": "claim",
            "color": "#000000",
        }
    )
    client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        json={"case_id": "CLM-tag-mismatch", "tag_ids": [str(tag_id)]},
        headers=get_auth_headers(),
    )
    await _insert_doc(test_db, case_id="CLM-tag-mismatch")
    prompt_id, _ = await _insert_prompt(test_db)
    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases/CLM-tag-mismatch/runs",
        json={"prompt_id": prompt_id},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_case_llm_run_enqueue_and_results(test_db, mock_auth):
    tag_id = ObjectId()
    await test_db.tags.insert_one(
        {
            "_id": tag_id,
            "organization_id": TEST_ORG_ID,
            "name": "claim",
            "color": "#000000",
        }
    )
    client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases",
        json={"case_id": "CLM-run", "tag_ids": [str(tag_id)]},
        headers=get_auth_headers(),
    )
    doc_id = await _insert_doc(test_db, case_id="CLM-run")
    prompt_id, rev_id = await _insert_prompt(test_db)
    await test_db.prompt_revisions.update_one(
        {"_id": ObjectId(rev_id)},
        {"$set": {"tag_ids": [str(tag_id)]}},
    )

    resp = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/cases/CLM-run/runs",
        json={"prompt_id": prompt_id},
        headers=get_auth_headers(),
    )
    assert resp.status_code == 202, resp.text
    assert resp.json().get("queue_message_id")

    aq = ad.common.get_analytiq_client()
    await ad.case_llm.save_case_llm_run(
        aq,
        organization_id=TEST_ORG_ID,
        case_id="CLM-run",
        prompt_id=prompt_id,
        prompt_revid=rev_id,
        prompt_version=1,
        document_ids=[str(doc_id)],
        llm_result={"summary": "ok"},
        run={"prompt": "x"},
        status="completed",
    )

    results = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/cases/CLM-run/results",
        params={"prompt_id": prompt_id},
        headers=get_auth_headers(),
    )
    assert results.status_code == 200, results.text
    body = results.json()
    assert body["case_run"]["llm_result"] == {"summary": "ok"}
    assert body["stale"] is False
    assert "documents" not in body


@pytest.mark.asyncio
async def test_case_llm_results_stale_when_membership_changes(test_db, mock_auth):
    _create_case("CLM-stale")
    doc_id = await _insert_doc(test_db, case_id="CLM-stale")
    prompt_id, rev_id = await _insert_prompt(test_db)
    aq = ad.common.get_analytiq_client()
    await ad.case_llm.save_case_llm_run(
        aq,
        organization_id=TEST_ORG_ID,
        case_id="CLM-stale",
        prompt_id=prompt_id,
        prompt_revid=rev_id,
        prompt_version=1,
        document_ids=[str(doc_id)],
        llm_result={"summary": "ok"},
        run=None,
        status="completed",
    )
    extra = await _insert_doc(test_db, case_id="CLM-stale")
    results = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/cases/CLM-stale/results",
        params={"prompt_id": prompt_id},
        headers=get_auth_headers(),
    )
    body = results.json()
    assert body["stale"] is True
    assert "membership" in body["stale_reasons"]
    assert extra  # used


@pytest.mark.asyncio
async def test_delete_case_removes_case_llm_runs(test_db, mock_auth):
    _create_case("CLM-del-runs")
    prompt_id, rev_id = await _insert_prompt(test_db)
    aq = ad.common.get_analytiq_client()
    await ad.case_llm.save_case_llm_run(
        aq,
        organization_id=TEST_ORG_ID,
        case_id="CLM-del-runs",
        prompt_id=prompt_id,
        prompt_revid=rev_id,
        prompt_version=1,
        document_ids=[],
        llm_result={},
        run=None,
        status="completed",
    )
    resp = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/cases/CLM-del-runs",
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200
    remaining = await test_db.case_llm_runs.count_documents({"case_id": "CLM-del-runs"})
    assert remaining == 0
