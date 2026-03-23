"""Tests that OCR org-scoped routes resolve documents within the path organization only."""
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest_utils import client, get_token_headers


@pytest.mark.asyncio
async def test_run_ocr_passes_organization_id_to_get_doc_and_queues_when_found(
    org_and_users, test_db
):
    """Successful run uses get_doc(..., organization_id) and enqueues OCR."""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    doc_id = "507f1f77bcf86cd799439011"

    with (
        patch(
            "analytiq_data.common.get_doc",
            new_callable=AsyncMock,
            return_value={"user_file_name": "test.pdf"},
        ) as mock_get_doc,
        patch(
            "analytiq_data.common.doc.update_doc_state",
            new_callable=AsyncMock,
        ),
        patch(
            "analytiq_data.queue.send_msg",
            new_callable=AsyncMock,
        ) as mock_send,
    ):
        resp = client.post(
            f"/v0/orgs/{org_id}/ocr/run/{doc_id}",
            headers=get_token_headers(admin["token"]),
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "queued", "document_id": doc_id}
    mock_get_doc.assert_called_once()
    assert mock_get_doc.call_args[0][2] == org_id
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_run_ocr_returns_404_when_document_not_in_org_does_not_enqueue(
    org_and_users, test_db
):
    """Foreign document ID cannot trigger state reset or OCR queue for another org."""
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    foreign_doc_id = "507f1f77bcf86cd799439011"

    with (
        patch("analytiq_data.common.get_doc", new_callable=AsyncMock, return_value=None),
        patch(
            "analytiq_data.common.doc.update_doc_state",
            new_callable=AsyncMock,
        ) as mock_update_state,
        patch(
            "analytiq_data.queue.send_msg",
            new_callable=AsyncMock,
        ) as mock_send,
    ):
        resp = client.post(
            f"/v0/orgs/{org_id}/ocr/run/{foreign_doc_id}",
            headers=get_token_headers(admin["token"]),
        )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"
    mock_update_state.assert_not_called()
    mock_send.assert_not_called()
