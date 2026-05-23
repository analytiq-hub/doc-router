from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import analytiq_data as ad
import pytest

from analytiq_data.flows.nodes.gmail.email_mime import encode_email_raw
from analytiq_data.flows.nodes.gmail.operations import execute_gmail_item


def test_encode_email_raw_produces_url_safe_base64() -> None:
    raw = encode_email_raw(
        to="<a@example.com>",
        subject="Hello",
        body_html="<p>Hi</p>",
    )
    assert "+" not in raw
    assert "/" not in raw


@pytest.mark.asyncio
async def test_message_send_calls_gmail_api(
    gmail_ctx: ad.flows.ExecutionContext,
    gmail_item: ad.flows.FlowItem,
    gmail_node_shell: dict[str, Any],
    mock_gmail_token,
    mock_gmail_api: AsyncMock,
) -> None:
    mock_gmail_api.return_value = {"id": "msg-1", "threadId": "t-1"}
    params = {
        "resource": "message",
        "operation": "send",
        "sendTo": "to@example.com",
        "subject": "Test",
        "emailType": "text",
        "message": "Body",
    }
    out = await execute_gmail_item(gmail_ctx, gmail_node_shell, params, gmail_item, item_index=0)
    assert out.json["id"] == "msg-1"
    mock_gmail_api.assert_awaited()
    call = mock_gmail_api.await_args
    assert call is not None
    assert call.args[1] == "POST"
    assert call.args[2] == "/gmail/v1/users/me/messages/send"
    body = call.kwargs.get("body") or {}
    assert "raw" in body


@pytest.mark.asyncio
async def test_message_get_all_returns_messages_wrapper(
    gmail_ctx: ad.flows.ExecutionContext,
    gmail_item: ad.flows.FlowItem,
    gmail_node_shell: dict[str, Any],
    mock_gmail_token,
    mock_gmail_api: AsyncMock,
) -> None:
    mock_gmail_api.side_effect = [
        {"messages": [{"id": "m1"}, {"id": "m2"}]},
        {"labels": [{"id": "INBOX", "name": "INBOX"}]},
        {
            "id": "m1",
            "threadId": "t1",
            "labelIds": ["INBOX"],
            "payload": {"headers": [{"name": "Subject", "value": "Hi"}]},
        },
        {
            "id": "m2",
            "threadId": "t1",
            "labelIds": ["INBOX"],
            "payload": {"headers": [{"name": "Subject", "value": "Bye"}]},
        },
    ]
    params = {
        "resource": "message",
        "operation": "getAll",
        "returnAll": False,
        "limit": 10,
        "simple": True,
        "filters": {"readStatus": "unread"},
    }
    out = await execute_gmail_item(gmail_ctx, gmail_node_shell, params, gmail_item, item_index=0)
    assert out.json["count"] == 2
    assert len(out.json["messages"]) == 2
    assert out.json["messages"][0]["Subject"] == "Hi"


@pytest.mark.asyncio
async def test_message_delete(
    gmail_ctx: ad.flows.ExecutionContext,
    gmail_item: ad.flows.FlowItem,
    gmail_node_shell: dict[str, Any],
    mock_gmail_token,
    mock_gmail_api: AsyncMock,
) -> None:
    mock_gmail_api.return_value = None
    params = {"resource": "message", "operation": "delete", "messageId": "m-del"}
    out = await execute_gmail_item(gmail_ctx, gmail_node_shell, params, gmail_item, item_index=0)
    assert out.json["success"] is True
    call = mock_gmail_api.await_args
    assert call is not None
    assert call.args[1] == "DELETE"
    assert call.args[2] == "/gmail/v1/users/me/messages/m-del"


@pytest.mark.asyncio
async def test_message_mark_as_read(
    gmail_ctx: ad.flows.ExecutionContext,
    gmail_item: ad.flows.FlowItem,
    gmail_node_shell: dict[str, Any],
    mock_gmail_token,
    mock_gmail_api: AsyncMock,
) -> None:
    mock_gmail_api.return_value = {"id": "m1", "labelIds": []}
    params = {"resource": "message", "operation": "markAsRead", "messageId": "m1"}
    out = await execute_gmail_item(gmail_ctx, gmail_node_shell, params, gmail_item, item_index=0)
    assert out.json["id"] == "m1"
    body = mock_gmail_api.await_args.kwargs.get("body") or {}
    assert body.get("removeLabelIds") == ["UNREAD"]


@pytest.mark.asyncio
async def test_label_create(
    gmail_ctx: ad.flows.ExecutionContext,
    gmail_item: ad.flows.FlowItem,
    gmail_node_shell: dict[str, Any],
    mock_gmail_token,
    mock_gmail_api: AsyncMock,
) -> None:
    mock_gmail_api.return_value = {"id": "Label_1", "name": "Work"}
    params = {"resource": "label", "operation": "create", "name": "Work"}
    out = await execute_gmail_item(gmail_ctx, gmail_node_shell, params, gmail_item, item_index=0)
    assert out.json["name"] == "Work"
    call = mock_gmail_api.await_args
    assert call is not None
    assert call.args[2] == "/gmail/v1/users/me/labels"


@pytest.mark.asyncio
async def test_message_reply_sends_in_thread(
    gmail_ctx: ad.flows.ExecutionContext,
    gmail_item: ad.flows.FlowItem,
    gmail_node_shell: dict[str, Any],
    mock_gmail_token,
    mock_gmail_api: AsyncMock,
) -> None:
    mock_gmail_api.side_effect = [
        {
            "threadId": "t-reply",
            "payload": {
                "headers": [
                    {"name": "From", "value": "boss@corp.com"},
                    {"name": "Subject", "value": "Status"},
                    {"name": "Message-ID", "value": "<orig@corp.com>"},
                ]
            },
        },
        {"emailAddress": "me@corp.com"},
        {"id": "sent-1", "threadId": "t-reply"},
    ]
    params = {
        "resource": "message",
        "operation": "reply",
        "messageId": "orig-msg",
        "emailType": "text",
        "message": "Done",
    }
    out = await execute_gmail_item(gmail_ctx, gmail_node_shell, params, gmail_item, item_index=0)
    assert out.json["threadId"] == "t-reply"
    send_call = mock_gmail_api.await_args_list[-1]
    body = send_call.kwargs.get("body") or {}
    assert body.get("threadId") == "t-reply"
    assert "raw" in body


@pytest.mark.asyncio
async def test_thread_trash(
    gmail_ctx: ad.flows.ExecutionContext,
    gmail_item: ad.flows.FlowItem,
    gmail_node_shell: dict[str, Any],
    mock_gmail_token,
    mock_gmail_api: AsyncMock,
) -> None:
    mock_gmail_api.return_value = {"id": "t1", "labelIds": ["TRASH"]}
    params = {"resource": "thread", "operation": "trash", "threadId": "t1"}
    out = await execute_gmail_item(gmail_ctx, gmail_node_shell, params, gmail_item, item_index=0)
    assert out.json["id"] == "t1"
    call = mock_gmail_api.await_args
    assert call is not None
    assert call.args[2] == "/gmail/v1/users/me/threads/t1/trash"
