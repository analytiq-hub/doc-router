import base64
import json
from datetime import datetime, UTC

import pytest
from bson import ObjectId

from .conftest_utils import client, TEST_ORG_ID, get_auth_headers


def _minimal_pdf_data_url(name: str) -> dict:
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    return {
        "name": name,
        "content": f"data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}",
    }


def _list_docs(params: dict) -> dict:
    resp = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        params=params,
        headers=get_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_documents_grid_sort_and_filters_focused(test_db, mock_auth):
    """
    Focused coverage for the new JSON `sort` and `filters` query params used by the UI grid.
    Ensures each supported "functionality" has at least one search or filter case that returns a known subset.
    """

    # Create tags
    cv_tag = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/tags",
        json={"name": "CV", "color": "#FF0000"},
        headers=get_auth_headers(),
    )
    assert cv_tag.status_code == 200, cv_tag.text
    cv_tag_id = cv_tag.json()["id"]

    finance_tag = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/tags",
        json={"name": "Finance", "color": "#00FF00"},
        headers=get_auth_headers(),
    )
    assert finance_tag.status_code == 200, finance_tag.text
    finance_tag_id = finance_tag.json()["id"]

    # Upload three documents (upload_date/uploaded_by/state are overridden below for determinism)
    up1 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [{**_minimal_pdf_data_url("Alpha CV.pdf"), "tag_ids": [cv_tag_id], "metadata": {"type": "cv"}}]},
        headers=get_auth_headers(),
    )
    assert up1.status_code == 200, up1.text
    doc1_id = up1.json()["documents"][0]["document_id"]

    up2 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [{**_minimal_pdf_data_url("Beta Invoice.pdf"), "tag_ids": [finance_tag_id], "metadata": {"type": "invoice"}}]},
        headers=get_auth_headers(),
    )
    assert up2.status_code == 200, up2.text
    doc2_id = up2.json()["documents"][0]["document_id"]

    up3 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [{**_minimal_pdf_data_url("Gamma Notes.pdf"), "tag_ids": [], "metadata": {"type": "notes"}}]},
        headers=get_auth_headers(),
    )
    assert up3.status_code == 200, up3.text
    doc3_id = up3.json()["documents"][0]["document_id"]

    # Make docs deterministic for sorting/filtering semantics
    docs = test_db["docs"]
    await docs.update_one(
        {"_id": ObjectId(doc1_id), "organization_id": TEST_ORG_ID},
        {"$set": {"uploaded_by": "alice@example.com", "state": "uploaded", "upload_date": datetime(2026, 1, 1, tzinfo=UTC)}},
    )
    await docs.update_one(
        {"_id": ObjectId(doc2_id), "organization_id": TEST_ORG_ID},
        {"$set": {"uploaded_by": "bob@example.com", "state": "ocr_failed", "upload_date": datetime(2026, 2, 1, tzinfo=UTC)}},
    )
    await docs.update_one(
        {"_id": ObjectId(doc3_id), "organization_id": TEST_ORG_ID},
        {"$set": {"uploaded_by": "charlie@example.com", "state": "uploaded", "upload_date": datetime(2026, 3, 1, tzinfo=UTC)}},
    )

    # --- Search: name_search (existing functionality) ---
    r = _list_docs({"name_search": "Alpha", "limit": 50})
    ids = {d["id"] for d in r["documents"]}
    assert doc1_id in ids
    assert doc2_id not in ids and doc3_id not in ids

    # --- Search/filter: metadata_search (existing functionality) ---
    r = _list_docs({"metadata_search": "type%3Dinvoice", "limit": 50})
    ids = {d["id"] for d in r["documents"]}
    assert ids == {doc2_id}

    # --- Filter: document_name contains (grid filters JSON) ---
    filters = {
        "items": [{"field": "document_name", "operator": "contains", "id": 1, "value": "Beta"}],
    }
    r = _list_docs({"filters": json.dumps(filters), "limit": 50})
    ids = {d["id"] for d in r["documents"]}
    assert ids == {doc2_id}

    # --- Filter: state equals (grid filters JSON) ---
    filters = {
        "items": [{"field": "state", "operator": "equals", "id": 2, "value": "ocr_failed"}],
    }
    r = _list_docs({"filters": json.dumps(filters), "limit": 50})
    ids = {d["id"] for d in r["documents"]}
    assert ids == {doc2_id}

    # --- Filter: uploaded_by contains (grid filters JSON) ---
    filters = {
        "items": [{"field": "uploaded_by", "operator": "contains", "id": 3, "value": "charlie"}],
    }
    r = _list_docs({"filters": json.dumps(filters), "limit": 50})
    ids = {d["id"] for d in r["documents"]}
    assert ids == {doc3_id}

    # --- Filter: upload_date after (grid filters JSON) ---
    filters = {
        "items": [{"field": "upload_date", "operator": "after", "id": 4, "value": "2026-02-15T00:00:00Z"}],
    }
    r = _list_docs({"filters": json.dumps(filters), "limit": 50})
    ids = {d["id"] for d in r["documents"]}
    assert ids == {doc3_id}

    # --- Filter: tag_ids contains (tag name lookup; grid filters JSON) ---
    # UI sends free-text. Backend interprets this as tag *name* search and maps to tag IDs.
    filters = {
        "items": [{"field": "tag_ids", "operator": "contains", "id": 5, "value": "CV"}],
    }
    r = _list_docs({"filters": json.dumps(filters), "limit": 50})
    ids = {d["id"] for d in r["documents"]}
    assert ids == {doc1_id}

    # --- Sort: multi-sort (grid sortModel JSON) ---
    sort = [
        {"field": "uploaded_by", "sort": "asc"},
        {"field": "upload_date", "sort": "desc"},
    ]
    r = _list_docs({"sort": json.dumps(sort), "limit": 50})
    got_order = [d["id"] for d in r["documents"]]
    # uploaded_by: alice, bob, charlie
    assert got_order.index(doc1_id) < got_order.index(doc2_id) < got_order.index(doc3_id)


@pytest.mark.asyncio
async def test_name_search_match_rank_exact_prefix_substring(test_db, mock_auth):
    """
    Rank 0 (exact) beats rank 1 (prefix) beats rank 2 (substring),
    even when the lower-ranked documents have a newer upload_date.

    Search term "a.txt":
      "a.txt"        → exact match (rank 0)
      "a.txt_v2.txt" → starts with "a.txt" (rank 1); os.path.splitext gives .txt
      "my_a.txt"     → contains "a.txt" at position 3 (rank 2)
    """
    docs_coll = test_db["docs"]

    up_exact = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [_minimal_pdf_data_url("a.txt")]},
        headers=get_auth_headers(),
    )
    assert up_exact.status_code == 200
    id_exact = up_exact.json()["documents"][0]["document_id"]

    up_prefix = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [_minimal_pdf_data_url("a.txt_v2.txt")]},
        headers=get_auth_headers(),
    )
    assert up_prefix.status_code == 200
    id_prefix = up_prefix.json()["documents"][0]["document_id"]

    up_substr = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [_minimal_pdf_data_url("my_a.txt")]},
        headers=get_auth_headers(),
    )
    assert up_substr.status_code == 200
    id_substr = up_substr.json()["documents"][0]["document_id"]

    # Give lower-ranked docs newer dates to prove rank dominates date
    await docs_coll.update_one({"_id": ObjectId(id_exact)}, {"$set": {"upload_date": datetime(2026, 1, 1, tzinfo=UTC)}})
    await docs_coll.update_one({"_id": ObjectId(id_prefix)}, {"$set": {"upload_date": datetime(2026, 2, 1, tzinfo=UTC)}})
    await docs_coll.update_one({"_id": ObjectId(id_substr)}, {"$set": {"upload_date": datetime(2026, 3, 1, tzinfo=UTC)}})

    r = _list_docs({"name_search": "a.txt", "limit": 50})
    ids = [d["id"] for d in r["documents"]]

    assert id_exact in ids and id_prefix in ids and id_substr in ids
    assert ids.index(id_exact) < ids.index(id_prefix), "exact must precede prefix"
    assert ids.index(id_prefix) < ids.index(id_substr), "prefix must precede substring"


@pytest.mark.asyncio
async def test_name_search_exact_beats_substring_older_doc(test_db, mock_auth):
    """
    '1.txt' (exact, older) should rank above '11.txt' (substring, newer).
    '11.txt' contains '1.txt' starting at position 1, so it is rank 2.
    """
    docs_coll = test_db["docs"]

    up_exact = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [_minimal_pdf_data_url("1.txt")]},
        headers=get_auth_headers(),
    )
    assert up_exact.status_code == 200
    id_exact = up_exact.json()["documents"][0]["document_id"]

    up_substr = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [_minimal_pdf_data_url("11.txt")]},
        headers=get_auth_headers(),
    )
    assert up_substr.status_code == 200
    id_substr = up_substr.json()["documents"][0]["document_id"]

    # 11.txt is much newer
    await docs_coll.update_one({"_id": ObjectId(id_exact)}, {"$set": {"upload_date": datetime(2026, 1, 1, tzinfo=UTC)}})
    await docs_coll.update_one({"_id": ObjectId(id_substr)}, {"$set": {"upload_date": datetime(2026, 6, 1, tzinfo=UTC)}})

    r = _list_docs({"name_search": "1.txt", "limit": 50})
    ids = [d["id"] for d in r["documents"]]

    assert id_exact in ids and id_substr in ids
    assert ids.index(id_exact) < ids.index(id_substr), "exact match must rank above substring even when older"


@pytest.mark.asyncio
async def test_name_search_same_rank_date_tiebreaker(test_db, mock_auth):
    """
    Two docs both at rank 2 (substring) are ordered by upload_date DESC.
    """
    docs_coll = test_db["docs"]

    up_old = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [_minimal_pdf_data_url("my_invoice_jan.pdf")]},
        headers=get_auth_headers(),
    )
    assert up_old.status_code == 200
    id_old = up_old.json()["documents"][0]["document_id"]

    up_new = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [_minimal_pdf_data_url("my_invoice_jun.pdf")]},
        headers=get_auth_headers(),
    )
    assert up_new.status_code == 200
    id_new = up_new.json()["documents"][0]["document_id"]

    await docs_coll.update_one({"_id": ObjectId(id_old)}, {"$set": {"upload_date": datetime(2026, 1, 1, tzinfo=UTC)}})
    await docs_coll.update_one({"_id": ObjectId(id_new)}, {"$set": {"upload_date": datetime(2026, 6, 1, tzinfo=UTC)}})

    r = _list_docs({"name_search": "invoice", "limit": 50})
    ids = [d["id"] for d in r["documents"]]

    assert id_old in ids and id_new in ids
    assert ids.index(id_new) < ids.index(id_old), "within same rank, newer upload_date should come first"


@pytest.mark.asyncio
async def test_name_search_case_insensitive_exact(test_db, mock_auth):
    """
    Case-insensitive exact match: searching 'A.TXT' gives rank 0 for 'a.txt'
    and rank 1 for 'a.txt_v2.txt' (prefix).  The older exact match must rank first.
    """
    docs_coll = test_db["docs"]

    up_exact = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [_minimal_pdf_data_url("a.txt")]},
        headers=get_auth_headers(),
    )
    assert up_exact.status_code == 200
    id_exact = up_exact.json()["documents"][0]["document_id"]

    up_prefix = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [_minimal_pdf_data_url("a.txt_v2.txt")]},
        headers=get_auth_headers(),
    )
    assert up_prefix.status_code == 200
    id_prefix = up_prefix.json()["documents"][0]["document_id"]

    # Prefix doc is newer
    await docs_coll.update_one({"_id": ObjectId(id_exact)}, {"$set": {"upload_date": datetime(2026, 1, 1, tzinfo=UTC)}})
    await docs_coll.update_one({"_id": ObjectId(id_prefix)}, {"$set": {"upload_date": datetime(2026, 6, 1, tzinfo=UTC)}})

    r = _list_docs({"name_search": "A.TXT", "limit": 50})
    ids = [d["id"] for d in r["documents"]]

    assert id_exact in ids and id_prefix in ids
    assert ids.index(id_exact) < ids.index(id_prefix), "case-insensitive exact match should rank first"

