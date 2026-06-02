"""Operation tests for ``flows.microsoft_outlook``."""

from __future__ import annotations

import pytest

import analytiq_data as ad

from analytiq_data.flows.nodes.microsoft_outlook.helpers import validate_resource_operation
from analytiq_data.flows.nodes.microsoft_outlook.operations import execute_microsoft_outlook_item

_OPS = "analytiq_data.flows.nodes.microsoft_outlook.operations"


def test_validate_unknown_resource() -> None:
    with pytest.raises(ValueError, match="Unknown Microsoft Outlook resource"):
        validate_resource_operation("mailbox", "send")


@pytest.mark.asyncio
async def test_message_send(
    outlook_ctx,
    outlook_item,
    outlook_node_shell,
    mock_outlook_auth,
    mock_outlook_request,
) -> None:
    mock_outlook_request.return_value = {}

    out = await execute_microsoft_outlook_item(
        outlook_ctx,
        outlook_node_shell,
        {
            "resource": "message",
            "operation": "send",
            "toRecipients": "a@example.com",
            "subject": "Hi",
            "bodyContent": "Hello",
        },
        outlook_item,
        item_index=0,
    )

    assert out.json.get("success") is True
    mock_outlook_request.assert_awaited_once()
    call = mock_outlook_request.await_args
    assert call.args[3] == "POST"
    assert call.args[4] == "/sendMail"
    body = call.kwargs.get("body") or {}
    assert body["message"]["subject"] == "Hi"


@pytest.mark.asyncio
async def test_message_get_all_simplified(
    outlook_ctx,
    outlook_item,
    outlook_node_shell,
    mock_outlook_auth,
) -> None:
    from unittest.mock import AsyncMock, patch

    rows = [
        {
            "id": "m1",
            "subject": "Test",
            "bodyPreview": "preview",
            "from": {"emailAddress": {"address": "from@example.com"}},
            "toRecipients": [{"emailAddress": {"address": "to@example.com"}}],
        }
    ]
    with patch(f"{_OPS}.outlook_request_all_items", new_callable=AsyncMock, return_value=rows):
        out = await execute_microsoft_outlook_item(
            outlook_ctx,
            outlook_node_shell,
            {"resource": "message", "operation": "getAll", "output": "simple"},
            outlook_item,
            item_index=0,
        )

    assert out.json["count"] == 1
    assert out.json["messages"][0]["from"] == "from@example.com"
