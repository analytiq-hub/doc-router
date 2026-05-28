"""Unit tests for Gmail trigger poll logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad

from analytiq_data.flows.nodes.gmail.poll_trigger import (
    LAST_TIME_CHECKED_KEY,
    POSSIBLE_DUPLICATES_KEY,
    _should_skip_message,
    poll_gmail_trigger,
)

_GMAIL = "analytiq_data.flows.nodes.gmail.poll_trigger"


def test_should_skip_draft_by_default() -> None:
    assert _should_skip_message({"labelIds": ["DRAFT"]}, include_drafts=False) is True
    assert _should_skip_message({"labelIds": ["DRAFT"]}, include_drafts=True) is False


def test_should_skip_sent_without_inbox() -> None:
    assert _should_skip_message({"labelIds": ["SENT"]}, include_drafts=False) is True
    assert _should_skip_message({"labelIds": ["SENT", "INBOX"]}, include_drafts=False) is False


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
        node_id="gm1",
        mode=mode,  # type: ignore[arg-type]
        analytiq_client=None,
        tick_meta={"testing": testing} if testing else {},
        static_data=dict(static or {}),
    )


def _node(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "gm1",
        "name": "Gmail Trigger",
        "type": "flows.trigger.gmail",
        "credentials": {"gmailOAuth2": "cred-1"},
        "parameters": params,
    }


@pytest.mark.asyncio
async def test_poll_schedule_enqueues_simplified_messages() -> None:
    ctx = _poll_ctx(static={LAST_TIME_CHECKED_KEY: 1_700_000_000})
    node = _node({"simple": True, "filters": {"readStatus": "unread", "q": "has:attachment"}})
    side_effect = [
        {"messages": [{"id": "m1"}]},
        {
            "id": "m1",
            "threadId": "t1",
            "internalDate": "1700000100000",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {"headers": [{"name": "Subject", "value": "Invoice"}]},
        },
        {"labels": [{"id": "INBOX", "name": "INBOX"}]},
    ]
    with patch(f"{_GMAIL}.resolve_oauth_access_token_for_org", new_callable=AsyncMock, return_value="tok"):
        with patch(f"{_GMAIL}._fetch_label_map", new_callable=AsyncMock, return_value={"INBOX": "INBOX"}):
            with patch(f"{_GMAIL}.gmail_api_request", new_callable=AsyncMock, side_effect=side_effect) as m:
                out = await poll_gmail_trigger(ctx, node)
    assert out is not None
    assert len(out[0]) == 1
    assert out[0][0].json["Subject"] == "Invoice"
    assert ctx.get_static(LAST_TIME_CHECKED_KEY) == 1_700_000_100
    list_call = m.await_args_list[0]
    qs = list_call.kwargs.get("query") or {}
    assert "has:attachment" in qs.get("q", "")
    assert "after:1700000000" in qs.get("q", "")


@pytest.mark.asyncio
async def test_poll_empty_schedule_returns_none() -> None:
    ctx = _poll_ctx(static={LAST_TIME_CHECKED_KEY: 1_700_000_000})
    node = _node({"simple": True, "filters": {}})
    with patch(f"{_GMAIL}.resolve_oauth_access_token_for_org", new_callable=AsyncMock, return_value="tok"):
        with patch(f"{_GMAIL}.gmail_api_request", new_callable=AsyncMock, return_value={"messages": []}):
            out = await poll_gmail_trigger(ctx, node)
    assert out is None


@pytest.mark.asyncio
async def test_poll_manual_no_data_raises() -> None:
    ctx = _poll_ctx(mode="manual")
    node = _node({"simple": True, "filters": {}})
    with patch(f"{_GMAIL}.resolve_oauth_access_token_for_org", new_callable=AsyncMock, return_value="tok"):
        with patch(f"{_GMAIL}.gmail_api_request", new_callable=AsyncMock, return_value={"messages": []}):
            with pytest.raises(ad.flows.FlowValidationError, match="No data"):
                await poll_gmail_trigger(ctx, node)


@pytest.mark.asyncio
async def test_poll_activation_testing_verifies_profile() -> None:
    ctx = _poll_ctx(testing=True)
    node = _node({"simple": True, "filters": {}})
    with patch(f"{_GMAIL}.resolve_oauth_access_token_for_org", new_callable=AsyncMock, return_value="tok"):
        with patch(f"{_GMAIL}.gmail_api_request", new_callable=AsyncMock, return_value={"emailAddress": "me@x.com"}) as m:
            out = await poll_gmail_trigger(ctx, node)
    assert out is None
    m.assert_awaited_once()
    assert m.await_args.args[2] == "/gmail/v1/users/me/profile"
    assert ctx.get_static(LAST_TIME_CHECKED_KEY)


@pytest.mark.asyncio
async def test_poll_deduplicates_possible_duplicates() -> None:
    ctx = _poll_ctx(
        static={
            LAST_TIME_CHECKED_KEY: 1_700_000_000,
            POSSIBLE_DUPLICATES_KEY: ["m1"],
        }
    )
    node = _node({"simple": True, "filters": {}})
    side_effect = [
        {"messages": [{"id": "m1"}, {"id": "m2"}]},
        {
            "id": "m1",
            "internalDate": "1700000100000",
            "labelIds": ["INBOX"],
            "payload": {"headers": []},
        },
        {
            "id": "m2",
            "internalDate": "1700000200000",
            "labelIds": ["INBOX"],
            "payload": {"headers": [{"name": "Subject", "value": "New"}]},
        },
        {"labels": []},
    ]
    with patch(f"{_GMAIL}.resolve_oauth_access_token_for_org", new_callable=AsyncMock, return_value="tok"):
        with patch(f"{_GMAIL}._fetch_label_map", new_callable=AsyncMock, return_value={}):
            with patch(f"{_GMAIL}.gmail_api_request", new_callable=AsyncMock, side_effect=side_effect):
                out = await poll_gmail_trigger(ctx, node)
    assert out is not None
    assert len(out[0]) == 1
    assert out[0][0].json["id"] == "m2"


@pytest.mark.asyncio
async def test_poll_resolves_token_via_for_org() -> None:
    ctx = _poll_ctx(testing=True)
    node = _node({"simple": True})
    for_org = AsyncMock(return_value="tok")
    exec_ctx_resolve = AsyncMock()
    with patch(f"{_GMAIL}.resolve_oauth_access_token_for_org", for_org):
        with patch(
            "analytiq_data.flows.nodes.gmail.api.resolve_oauth_access_token",
            exec_ctx_resolve,
        ):
            with patch(f"{_GMAIL}.gmail_api_request", new_callable=AsyncMock, return_value={"emailAddress": "a@b.c"}):
                await poll_gmail_trigger(ctx, node)
    for_org.assert_awaited_once_with("org1", node)
    exec_ctx_resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_trigger_node_execute_replays_items() -> None:
    ad.flows.register_builtin_nodes()
    nt = ad.flows.get("flows.trigger.gmail")
    ctx = ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="schedule",
        trigger_data={
            "type": "poll",
            "items": [[{"json": {"id": "m1"}, "binary": {}, "meta": {}, "paired_item": None}]],
        },
        run_data={},
        analytiq_client=None,
    )
    node = {"id": "gm1", "name": "Gmail", "type": "flows.trigger.gmail", "parameters": {}}
    out = await nt.execute(ctx, node, [[]])
    assert out[0][0].json["id"] == "m1"
