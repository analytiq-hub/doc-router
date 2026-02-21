import pytest
from tests.conftest_utils import client, get_token_headers

@pytest.mark.asyncio
async def test_doc_permissions(org_and_users, test_db):
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    member = org_and_users["member"]
    outsider = org_and_users["outsider"]

    pdf_content = "data:application/pdf;base64,JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiAwIG9iago8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PgplbmRvYmoKMyAwIG9iago8PC9UeXBlL1BhZ2UvUGFyZW50IDIgMCBSL1Jlc291cmNlczw8Pj4vTWVkaWFCb3hbMCAwIDYxMiA3OTJdL0NvbnRlbnRzIDQgMCBSPj4KZW5kb2JqCjQgMCBvYmoKPDwvTGVuZ3RoIDUgPj4Kc3RyZWFtCkJUClRFU1QKZW5kc3RyZWFtCmVuZG9iagp4cmVmCjAgNQowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMTAgMDAwMDAgbiAKMDAwMDAwMDAyMCAwMDAwMCBuIAowMDAwMDAwMDMwIDAwMDAwIG4gCjAwMDAwMDAwNDAgMDAwMDAgbiAKdHJhaWxlcgo8PC9TaXplIDUvUm9vdCAxIDAgUi9JbmZvIDYgMCBSCj4+CnN0YXJ0eHJlZgo2NTU1CiUlRU9G"
    upload_data = {
        "documents": [
            {
                "name": "test.pdf",
                "content": pdf_content,
                "tag_ids": [],
                "metadata": {"test_type": "auth_test"}
            }
        ]
    }

    # --- CREATE ---
    resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Admin should be able to create document, got {resp.status_code}: {resp.text}"
    doc_id = resp.json()["documents"][0]["document_id"]

    resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_token_headers(member["token"]))
    assert resp.status_code == 200, f"Member should be able to create document, got {resp.status_code}: {resp.text}"

    resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to create document, got {resp.status_code}: {resp.text}"

    # --- LIST ---
    resp = client.get(f"/v0/orgs/{org_id}/documents", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Admin should be able to list documents, got {resp.status_code}: {resp.text}"

    resp = client.get(f"/v0/orgs/{org_id}/documents", headers=get_token_headers(member["token"]))
    assert resp.status_code == 200, f"Member should be able to list documents, got {resp.status_code}: {resp.text}"

    resp = client.get(f"/v0/orgs/{org_id}/documents", headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to list documents, got {resp.status_code}: {resp.text}"

    # --- GET ---
    resp = client.get(f"/v0/orgs/{org_id}/documents/{doc_id}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Admin should be able to get document, got {resp.status_code}: {resp.text}"

    resp = client.get(f"/v0/orgs/{org_id}/documents/{doc_id}", headers=get_token_headers(member["token"]))
    assert resp.status_code == 200, f"Member should be able to get document, got {resp.status_code}: {resp.text}"

    resp = client.get(f"/v0/orgs/{org_id}/documents/{doc_id}", headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403, 404), f"Outsider should NOT be able to get document, got {resp.status_code}: {resp.text}"

    # --- GET metadata (no content) ---
    resp = client.get(f"/v0/orgs/{org_id}/documents/{doc_id}/metadata", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Admin should be able to get document metadata, got {resp.status_code}: {resp.text}"
    assert "content" not in resp.json(), "Metadata endpoint must not return content"

    resp = client.get(f"/v0/orgs/{org_id}/documents/{doc_id}/metadata", headers=get_token_headers(member["token"]))
    assert resp.status_code == 200, f"Member should be able to get document metadata, got {resp.status_code}: {resp.text}"

    resp = client.get(f"/v0/orgs/{org_id}/documents/{doc_id}/metadata", headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403, 404), f"Outsider should NOT be able to get document metadata, got {resp.status_code}: {resp.text}"

    # --- UPDATE ---
    update_data = {"document_name": "newname.pdf", "metadata": {"test_type": "auth_test", "updated": "true"}}
    resp = client.put(f"/v0/orgs/{org_id}/documents/{doc_id}", json=update_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Admin should be able to update document, got {resp.status_code}: {resp.text}"

    resp = client.put(f"/v0/orgs/{org_id}/documents/{doc_id}", json=update_data, headers=get_token_headers(member["token"]))
    assert resp.status_code == 200, f"Member should be able to update document, got {resp.status_code}: {resp.text}"

    resp = client.put(f"/v0/orgs/{org_id}/documents/{doc_id}", json=update_data, headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403, 404), f"Outsider should NOT be able to update document, got {resp.status_code}: {resp.text}"

    # --- DELETE ---
    resp = client.delete(f"/v0/orgs/{org_id}/documents/{doc_id}", headers=get_token_headers(member["token"]))
    assert resp.status_code == 200, f"Member should be able to delete document, got {resp.status_code}: {resp.text}"

    # Re-upload for admin delete test
    resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_token_headers(admin["token"]))
    doc_id = resp.json()["documents"][0]["document_id"]

    resp = client.delete(f"/v0/orgs/{org_id}/documents/{doc_id}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Admin should be able to delete document, got {resp.status_code}: {resp.text}"

    resp = client.delete(f"/v0/orgs/{org_id}/documents/{doc_id}", headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403, 404), f"Outsider should NOT be able to delete document, got {resp.status_code}: {resp.text}" 