from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad

from analytiq_data.flows.nodes.microsoft_outlook.helpers import prepare_trigger_filters
from analytiq_data.flows.nodes.microsoft_outlook.poll_trigger import (
    LAST_TIME_CHECKED_KEY,
    poll_microsoft_outlook_trigger,
)

_POLL = "analytiq_data.flows.nodes.microsoft_outlook.poll_trigger"


def test_prepare_trigger_filters_read_status() -> None:
    filt = prepare_trigger_filters({"readStatus": "unread", "sender": "a@b.com"})
    assert filt is not None
    assert "isRead eq false" in filt
    assert "from/emailAddress/address eq 'a@b.com'" in filt


def _poll_ctx(
    *,
    mode: str = "schedule",
    testing: bool = False,
    static: dict | None = None,
) -> ad.flows.PollContext:
    return ad.flows.PollContext(
        organization_id="org1",
        flow_id="flow1",
        flow_revid="rev1",
        node_id="ol1",
        mode=mode,  # type: ignore[arg-type]
        analytiq_client=None,
        tick_meta={"testing": testing} if testing else {},
        static_data=dict(static or {}),
    )


def _node(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "ol1",
        "name": "Microsoft Outlook Trigger",
        "type": "flows.trigger.microsoft_outlook",
        "credentials": {"microsoftOutlookOAuth2Api": "cred-1"},
        "parameters": params,
    }


@pytest.mark.asyncio
async def test_poll_schedule_error_does_not_advance_checkpoint() -> None:
    checkpoint = "2026-05-21T10:00:00+00:00"
    ctx = _poll_ctx(static={LAST_TIME_CHECKED_KEY: checkpoint})
    node = _node({"output": "simple", "filters": {"readStatus": "both"}})
    with (
        patch(
            f"{_POLL}.resolve_outlook_auth_for_org",
            new_callable=AsyncMock,
            return_value=("tok", {}, "https://graph.microsoft.com/v1.0/me"),
        ),
        patch(
            f"{_POLL}.outlook_request_all_items",
            new_callable=AsyncMock,
            side_effect=RuntimeError("graph down"),
        ),
    ):
        out = await poll_microsoft_outlook_trigger(ctx, node)
    assert out is None
    assert ctx.get_static(LAST_TIME_CHECKED_KEY) == checkpoint


@pytest.mark.asyncio
async def test_poll_first_run_establishes_baseline() -> None:
    ctx = _poll_ctx()
    node = _node({"output": "simple"})
    with patch(
        f"{_POLL}.resolve_outlook_auth_for_org",
        new_callable=AsyncMock,
        return_value=("tok", {}, "https://graph.microsoft.com/v1.0/me"),
    ):
        out = await poll_microsoft_outlook_trigger(ctx, node)
    assert out is None
    assert ctx.get_static(LAST_TIME_CHECKED_KEY) is not None


@pytest.mark.asyncio
async def test_poll_schedule_returns_messages() -> None:
    ctx = _poll_ctx(static={LAST_TIME_CHECKED_KEY: "2026-05-21T10:00:00+00:00"})
    node = _node({"output": "simple", "filters": {"readStatus": "both"}})
    rows = [
        {
            "id": "m1",
            "subject": "Hello",
            "bodyPreview": "Hi",
            "from": {"emailAddress": {"address": "from@example.com"}},
            "toRecipients": [{"emailAddress": {"address": "to@example.com"}}],
        }
    ]
    with (
        patch(
            f"{_POLL}.resolve_outlook_auth_for_org",
            new_callable=AsyncMock,
            return_value=("tok", {}, "https://graph.microsoft.com/v1.0/me"),
        ),
        patch(
            f"{_POLL}.outlook_request_all_items",
            new_callable=AsyncMock,
            return_value=rows,
        ),
    ):
        out = await poll_microsoft_outlook_trigger(ctx, node)
    assert out is not None
    assert len(out[0]) == 1
    assert out[0][0].json["subject"] == "Hello"
    assert out[0][0].json["from"] == "from@example.com"


@pytest.mark.asyncio
async def test_poll_simple_output_skips_binary_download() -> None:
    ctx = _poll_ctx(static={LAST_TIME_CHECKED_KEY: "2026-05-21T10:00:00+00:00"})
    node = _node({"output": "simple", "filters": {"readStatus": "both"}})
    rows = [
        {
            "id": "m1",
            "subject": "Hi",
            "hasAttachments": True,
            "from": {"emailAddress": {"address": "from@example.com"}},
            "toRecipients": [{"emailAddress": {"address": "to@example.com"}}],
        }
    ]
    with (
        patch(
            f"{_POLL}.resolve_outlook_auth_for_org",
            new_callable=AsyncMock,
            return_value=("tok", {}, "https://graph.microsoft.com/v1.0/me"),
        ),
        patch(
            f"{_POLL}.outlook_request_all_items",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            f"{_POLL}.download_message_attachments",
            new_callable=AsyncMock,
        ) as dl,
    ):
        out = await poll_microsoft_outlook_trigger(ctx, node)
    assert out is not None
    assert out[0][0].binary == {}
    dl.assert_not_called()


@pytest.mark.asyncio
async def test_poll_download_attachments_populates_binary() -> None:
    ctx = _poll_ctx(static={LAST_TIME_CHECKED_KEY: "2026-05-21T10:00:00+00:00"})
    node = _node({"output": "raw", "filters": {"readStatus": "both"}})
    rows = [{"id": "m1", "subject": "With file", "hasAttachments": True}]
    fake_binary = {
        "attachment_0": ad.flows.BinaryRef(
            mime_type="text/plain",
            file_name="a.txt",
            data=b"data",
        )
    }
    with (
        patch(
            f"{_POLL}.resolve_outlook_auth_for_org",
            new_callable=AsyncMock,
            return_value=("tok", {}, "https://graph.microsoft.com/v1.0/me"),
        ),
        patch(
            f"{_POLL}.outlook_request_all_items",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            f"{_POLL}.download_message_attachments",
            new_callable=AsyncMock,
            return_value=fake_binary,
        ),
    ):
        out = await poll_microsoft_outlook_trigger(ctx, node)
    assert out is not None
    assert out[0][0].binary.get("attachment_0") is not None
    assert out[0][0].binary["attachment_0"].data == b"data"


@pytest.mark.asyncio
async def test_poll_manual_returns_latest() -> None:
    ctx = _poll_ctx(mode="manual")
    node = _node({"output": "raw"})
    page = {
        "value": [
            {"id": "m1", "subject": "Latest", "hasAttachments": True},
        ]
    }
    with (
        patch(
            f"{_POLL}.resolve_outlook_auth_for_org",
            new_callable=AsyncMock,
            return_value=("tok", {}, "https://graph.microsoft.com/v1.0/me"),
        ),
        patch(
            f"{_POLL}.outlook_request",
            new_callable=AsyncMock,
            return_value=page,
        ) as req,
        patch(
            f"{_POLL}.download_message_attachments",
            new_callable=AsyncMock,
            return_value={
                "attachment_0": ad.flows.BinaryRef(
                    mime_type="text/plain", file_name="a.txt", data=b"x"
                )
            },
        ) as dl,
    ):
        out = await poll_microsoft_outlook_trigger(ctx, node)
    assert out is not None
    assert out[0][0].json["subject"] == "Latest"
    assert out[0][0].binary["attachment_0"].data == b"x"
    call_qs = req.call_args.kwargs.get("query") or req.call_args[1].get("query")
    assert call_qs.get("$orderby") == "receivedDateTime desc"
    dl.assert_awaited_once()
