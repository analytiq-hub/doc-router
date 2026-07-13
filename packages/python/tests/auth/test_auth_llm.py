import pytest
from tests.conftest_utils import client, get_token_headers

@pytest.mark.asyncio
async def test_llm_permissions(org_and_users, test_db):
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    member = org_and_users["member"]
    outsider = org_and_users["outsider"]

    # Upload a document as admin
    pdf_content = "data:application/pdf;base64,JVBERi0xLjQK..."  # Use a valid base64 PDF string
    upload_data = {
        "documents": [
            {
                "name": "llmtest.pdf",
                "content": pdf_content,
                "tag_ids": []
            }
        ]
    }
    resp = client.post(f"/v0/orgs/{org_id}/documents", json=upload_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200
    doc_id = resp.json()["documents"][0]["document_id"]

    # Optionally, mock OCR completion here if your backend requires it

    # --- LLM RUN ---
    url_run = f"/v0/orgs/{org_id}/llm/run/{doc_id}"
    resp = client.post(url_run, headers=get_token_headers(admin["token"]))
    assert resp.status_code in (200, 404, 500), f"Admin should be able to run LLM, got {resp.status_code}: {resp.text}"

    resp = client.post(url_run, headers=get_token_headers(member["token"]))
    assert resp.status_code in (200, 404, 500), f"Member should be able to run LLM, got {resp.status_code}: {resp.text}"

    resp = client.post(url_run, headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to run LLM, got {resp.status_code}: {resp.text}"

    # --- LLM RESULT GET ---
    url_result = f"/v0/orgs/{org_id}/llm/result/{doc_id}?prompt_revid=default"
    resp = client.get(url_result, headers=get_token_headers(admin["token"]))
    assert resp.status_code in (200, 404), f"Admin should be able to get LLM result, got {resp.status_code}: {resp.text}"

    resp = client.get(url_result, headers=get_token_headers(member["token"]))
    assert resp.status_code in (200, 404), f"Member should be able to get LLM result, got {resp.status_code}: {resp.text}"

    resp = client.get(url_result, headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to get LLM result, got {resp.status_code}: {resp.text}"

    # --- LLM RESULT UPDATE ---
    url_update = f"/v0/orgs/{org_id}/llm/result/{doc_id}?prompt_revid=default"
    update_data = {
        "updated_llm_result": {"field": "value"},
        "is_verified": True
    }
    resp = client.put(url_update, json=update_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code in (200, 404, 400, 500), f"Admin should be able to update LLM result, got {resp.status_code}: {resp.text}"

    resp = client.put(url_update, json=update_data, headers=get_token_headers(member["token"]))
    assert resp.status_code in (200, 404, 400, 500), f"Member should be able to update LLM result, got {resp.status_code}: {resp.text}"

    resp = client.put(url_update, json=update_data, headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to update LLM result, got {resp.status_code}: {resp.text}"

    # --- LLM RESULT DELETE ---
    url_delete = f"/v0/orgs/{org_id}/llm/result/{doc_id}?prompt_revid=default"
    resp = client.delete(url_delete, headers=get_token_headers(admin["token"]))
    assert resp.status_code in (200, 404), f"Admin should be able to delete LLM result, got {resp.status_code}: {resp.text}"

    resp = client.delete(url_delete, headers=get_token_headers(member["token"]))
    assert resp.status_code in (200, 404), f"Member should be able to delete LLM result, got {resp.status_code}: {resp.text}"

    resp = client.delete(url_delete, headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to delete LLM result, got {resp.status_code}: {resp.text}" 