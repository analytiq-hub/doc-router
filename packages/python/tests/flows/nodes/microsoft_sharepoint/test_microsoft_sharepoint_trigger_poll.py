from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad

from analytiq_data.flows.nodes.microsoft_sharepoint.poll_trigger import (
    LAST_LINK_KEY,
    LAST_TIME_CHECKED_KEY,
    poll_microsoft_sharepoint_trigger,
)

_POLL = "analytiq_data.flows.nodes.microsoft_sharepoint.poll_trigger"


def _poll_ctx(
    *,
    mode: str = "schedule",
    static: dict | None = None,
) -> ad.flows.PollContext:
    return ad.flows.PollContext(
        organization_id="org1",
        flow_id="flow1",
        flow_revid="rev1",
        node_id="sp1",
        mode=mode,  # type: ignore[arg-type]
        analytiq_client=None,
        tick_meta={},
        static_data=dict(static or {}),
    )


def _node(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "sp1",
        "name": "Microsoft SharePoint Trigger",
        "type": "flows.trigger.microsoft_sharepoint",
        "credentials": {"microsoftSharePointOAuth2Api": "cred-1"},
        "parameters": params,
    }


@pytest.mark.asyncio
async def test_poll_schedule_returns_items() -> None:
    ctx = _poll_ctx(static={LAST_TIME_CHECKED_KEY: "2026-05-21T10:00:00+00:00"})
    node = _node({"siteId": "root", "event": "fileCreated", "simple": False})
    items = [
        {
            "id": "f1",
            "file": {"mimeType": "text/plain"},
            "fileSystemInfo": {
                "createdDateTime": "2026-05-21T12:00:00Z",
                "lastModifiedDateTime": "2026-05-21T12:00:00Z",
            },
        }
    ]
    with (
        patch(
            f"{_POLL}.resolve_sharepoint_subdomain_for_org",
            new_callable=AsyncMock,
            return_value="contoso",
        ),
        patch(
            f"{_POLL}.resolve_oauth_access_token_for_org",
            new_callable=AsyncMock,
            return_value="tok",
        ),
        patch(
            f"{_POLL}.graph_request_all_items_delta",
            new_callable=AsyncMock,
            return_value=(
                "https://contoso.sharepoint.com/_api/v2.0/delta-next",
                items,
            ),
        ),
    ):
        out = await poll_microsoft_sharepoint_trigger(ctx, node)
    assert out is not None
    assert len(out[0]) == 1
    assert out[0][0].json["id"] == "f1"
    assert (
        ctx.get_static(LAST_LINK_KEY)
        == "https://contoso.sharepoint.com/_api/v2.0/delta-next"
    )
