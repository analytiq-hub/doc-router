from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import analytiq_data as ad
import pytest


@pytest.mark.asyncio
async def test_node_execute_drive_get(
    drive_ctx: ad.flows.ExecutionContext,
    drive_item: ad.flows.FlowItem,
    drive_node_shell: dict[str, Any],
) -> None:
    ad.flows.register_builtin_nodes()
    nt = ad.flows.get("flows.google_drive")
    node = {
        **drive_node_shell,
        "parameters": {
            "authentication": "oAuth2",
            "resource": "drive",
            "operation": "get",
            "driveId": "abc123",
        },
    }
    with (
        patch(
            "analytiq_data.flows.nodes.google_drive.operations.resolve_oauth_access_token",
            new_callable=AsyncMock,
            return_value="tok",
        ),
        patch(
            "analytiq_data.flows.nodes.google_drive.operations.google_api_request",
            new_callable=AsyncMock,
            return_value={"id": "abc123", "name": "Team Drive"},
        ) as mock_req,
    ):
        out = await nt.execute(drive_ctx, node, [[drive_item]])
    assert len(out[0]) == 1
    assert out[0][0].json["name"] == "Team Drive"
    mock_req.assert_awaited_once()
    assert mock_req.await_args.args[2] == "/drive/v3/drives/abc123"


@pytest.mark.asyncio
async def test_node_execute_continue_on_fail_returns_error_json(
    drive_ctx: ad.flows.ExecutionContext,
    drive_item: ad.flows.FlowItem,
    drive_node_shell: dict[str, Any],
) -> None:
    ad.flows.register_builtin_nodes()
    nt = ad.flows.get("flows.google_drive")
    node = {
        **drive_node_shell,
        "continueOnFail": True,
        "parameters": {
            "resource": "drive",
            "operation": "get",
            "driveId": "missing",
        },
    }
    with (
        patch(
            "analytiq_data.flows.nodes.google_drive.operations.resolve_oauth_access_token",
            new_callable=AsyncMock,
            return_value="tok",
        ),
        patch(
            "analytiq_data.flows.nodes.google_drive.operations.google_api_request",
            new_callable=AsyncMock,
            side_effect=RuntimeError("API down"),
        ),
    ):
        out = await nt.execute(drive_ctx, node, [[drive_item]])
    assert out[0][0].json["error"] == "API down"
    assert out[0][0].meta == drive_item.meta
