from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad

from analytiq_data.flows.integrations.microsoft import normalize_drive_item_id
from analytiq_data.flows.nodes.microsoft_onedrive.poll_trigger import (
    LAST_LINK_KEY,
    LAST_TIME_CHECKED_KEY,
    poll_microsoft_onedrive_trigger,
)

_POLL = "analytiq_data.flows.nodes.microsoft_onedrive.poll_trigger"


def test_normalize_drive_item_id_from_url() -> None:
    url = "https://onedrive.live.com/?id=ABC%21123&cid=xyz"
    assert normalize_drive_item_id(url) == "ABC!123"


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
        node_id="od1",
        mode=mode,  # type: ignore[arg-type]
        analytiq_client=None,
        tick_meta={"testing": testing} if testing else {},
        static_data=dict(static or {}),
    )


def _node(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "od1",
        "name": "Microsoft OneDrive Trigger",
        "type": "flows.trigger.microsoft_onedrive",
        "credentials": {"microsoftOneDriveOAuth2Api": "cred-1"},
        "parameters": params,
    }


@pytest.mark.asyncio
async def test_poll_schedule_returns_items() -> None:
    ctx = _poll_ctx(static={LAST_TIME_CHECKED_KEY: "2026-05-21T10:00:00+00:00"})
    node = _node({"event": "fileCreated", "simple": False})
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
            f"{_POLL}.resolve_oauth_access_token_for_org",
            new_callable=AsyncMock,
            return_value="tok",
        ),
        patch(
            f"{_POLL}.graph_request_all_items_delta",
            new_callable=AsyncMock,
            return_value=("https://graph.microsoft.com/delta-next", items),
        ),
    ):
        out = await poll_microsoft_onedrive_trigger(ctx, node)
    assert out is not None
    assert len(out[0]) == 1
    assert out[0][0].json["id"] == "f1"
    assert ctx.get_static(LAST_LINK_KEY) == "https://graph.microsoft.com/delta-next"


@pytest.mark.asyncio
async def test_poll_manual_no_matches_raises() -> None:
    ctx = _poll_ctx(mode="manual")
    node = _node({"event": "fileCreated"})
    with (
        patch(
            f"{_POLL}.resolve_oauth_access_token_for_org",
            new_callable=AsyncMock,
            return_value="tok",
        ),
        patch(
            f"{_POLL}.graph_request",
            new_callable=AsyncMock,
            return_value={"value": []},
        ),
        pytest.raises(ad.flows.FlowValidationError, match="No data with the current filter"),
    ):
        await poll_microsoft_onedrive_trigger(ctx, node)


@pytest.mark.asyncio
async def test_poll_testing_probes_delta_then_optional_file() -> None:
    ctx = _poll_ctx(testing=True)
    node = _node(
        {
            "event": "fileUpdated",
            "watch": "selectedFile",
            "fileId": "item-99",
        }
    )
    with (
        patch(
            f"{_POLL}.resolve_oauth_access_token_for_org",
            new_callable=AsyncMock,
            return_value="tok",
        ),
        patch(
            f"{_POLL}.graph_request",
            new_callable=AsyncMock,
            side_effect=[
                {"@odata.deltaLink": "https://graph.microsoft.com/delta"},
                {"id": "item-99"},
            ],
        ) as mock_req,
    ):
        out = await poll_microsoft_onedrive_trigger(ctx, node)
    assert out is None
    assert mock_req.await_count == 2


@pytest.mark.asyncio
async def test_poll_testing_spo_error_is_actionable() -> None:
    from analytiq_data.flows.integrations.microsoft import MicrosoftGraphApiError

    ctx = _poll_ctx(testing=True)
    node = _node({"event": "fileCreated"})
    with (
        patch(
            f"{_POLL}.resolve_oauth_access_token_for_org",
            new_callable=AsyncMock,
            return_value="tok",
        ),
        patch(
            f"{_POLL}.graph_request",
            new_callable=AsyncMock,
            side_effect=MicrosoftGraphApiError(
                "bad",
                status_code=400,
                graph_message="Tenant does not have a SPO license.",
            ),
        ),
        pytest.raises(ad.flows.FlowValidationError, match="SharePoint Online"),
    ):
        await poll_microsoft_onedrive_trigger(ctx, node)
