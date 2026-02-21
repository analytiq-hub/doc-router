import pytest
from tests.conftest_utils import client, get_token_headers

@pytest.mark.asyncio
async def test_ocr_permissions(org_and_users, test_db):
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
                "tag_ids": []
            }
        ]
    }

    # Upload a document as admin
    resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    doc_id = resp.json()["documents"][0]["document_id"]

    # --- OCR BLOCKS ---
    url_blocks = f"/v0/orgs/{org_id}/ocr/download/blocks/{doc_id}"
    resp = client.get(url_blocks, headers=get_token_headers(admin["token"]))
    assert resp.status_code in (200, 404), f"Admin should be able to access OCR blocks, got {resp.status_code}: {resp.text}"

    resp = client.get(url_blocks, headers=get_token_headers(member["token"]))
    assert resp.status_code in (200, 404), f"Member should be able to access OCR blocks, got {resp.status_code}: {resp.text}"

    resp = client.get(url_blocks, headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to access OCR blocks, got {resp.status_code}: {resp.text}"

    # OCR blocks with format=gzip (same permissions as plain)
    resp = client.get(url_blocks, params={"format": "gzip"}, headers=get_token_headers(admin["token"]))
    assert resp.status_code in (200, 404), f"Admin should be able to access OCR blocks (gzip), got {resp.status_code}: {resp.text}"

    # --- OCR TEXT ---
    url_text = f"/v0/orgs/{org_id}/ocr/download/text/{doc_id}"
    resp = client.get(url_text, headers=get_token_headers(admin["token"]))
    assert resp.status_code in (200, 404), f"Admin should be able to access OCR text, got {resp.status_code}: {resp.text}"

    resp = client.get(url_text, headers=get_token_headers(member["token"]))
    assert resp.status_code in (200, 404), f"Member should be able to access OCR text, got {resp.status_code}: {resp.text}"

    resp = client.get(url_text, headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to access OCR text, got {resp.status_code}: {resp.text}"

    # --- OCR METADATA ---
    url_metadata = f"/v0/orgs/{org_id}/ocr/download/metadata/{doc_id}"
    resp = client.get(url_metadata, headers=get_token_headers(admin["token"]))
    assert resp.status_code in (200, 404), f"Admin should be able to access OCR metadata, got {resp.status_code}: {resp.text}"

    resp = client.get(url_metadata, headers=get_token_headers(member["token"]))
    assert resp.status_code in (200, 404), f"Member should be able to access OCR metadata, got {resp.status_code}: {resp.text}"

    resp = client.get(url_metadata, headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to access OCR metadata, got {resp.status_code}: {resp.text}" 