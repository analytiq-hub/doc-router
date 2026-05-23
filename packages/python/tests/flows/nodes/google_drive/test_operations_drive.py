from __future__ import annotations

from typing import Any

import analytiq_data as ad
import pytest

from analytiq_data.flows.nodes.google_drive.operations import execute_google_drive_item


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "params", "method", "path"),
    [
        ("create", {"name": "Team"}, "POST", "/drive/v3/drives"),
        ("get", {"driveId": "abc123"}, "GET", "/drive/v3/drives/abc123"),
        ("update", {"driveId": "abc123", "options": {"name": "Renamed"}}, "PATCH", "/drive/v3/drives/abc123"),
        ("deleteDrive", {"driveId": "abc123"}, "DELETE", "/drive/v3/drives/abc123"),
    ],
)
async def test_drive_operations_call_expected_api(
    drive_ctx: ad.flows.ExecutionContext,
    drive_item: ad.flows.FlowItem,
    drive_node_shell: dict[str, Any],
    mock_oauth_token,
    mock_gd_api,
    operation: str,
    params: dict[str, Any],
    method: str,
    path: str,
) -> None:
    mock_gd_api.return_value = {"id": "abc123", "name": "Team Drive"}
    merged = {"resource": "drive", "operation": operation, **params}
    out = await execute_google_drive_item(drive_ctx, drive_node_shell, merged, drive_item, item_index=0)
    assert isinstance(out, ad.flows.FlowItem)
    mock_gd_api.assert_awaited()
    assert mock_gd_api.await_args.args[1] == method
    assert mock_gd_api.await_args.args[2] == path


@pytest.mark.asyncio
async def test_drive_list_uses_files_list_endpoint(
    drive_ctx: ad.flows.ExecutionContext,
    drive_item: ad.flows.FlowItem,
    drive_node_shell: dict[str, Any],
    mock_oauth_token,
    mock_gd_api,
) -> None:
    mock_gd_api.return_value = {"drives": [{"id": "d1"}]}
    params = {"resource": "drive", "operation": "list", "limit": 10}
    out = await execute_google_drive_item(drive_ctx, drive_node_shell, params, drive_item, item_index=0)
    assert out.json["drives"][0]["id"] == "d1"
    assert mock_gd_api.await_args.args[1] == "GET"
    assert mock_gd_api.await_args.args[2] == "/drive/v3/drives"


@pytest.mark.asyncio
async def test_drive_list_return_all_uses_pagination_helper(
    drive_ctx: ad.flows.ExecutionContext,
    drive_item: ad.flows.FlowItem,
    drive_node_shell: dict[str, Any],
    mock_oauth_token,
    mock_gd_api_all_items,
) -> None:
    mock_gd_api_all_items.return_value = [{"id": "d1"}, {"id": "d2"}]
    params = {"resource": "drive", "operation": "list", "returnAll": True}
    out = await execute_google_drive_item(drive_ctx, drive_node_shell, params, drive_item, item_index=0)
    assert out.json["drives"] == [{"id": "d1"}, {"id": "d2"}]
    mock_gd_api_all_items.assert_awaited_once()
