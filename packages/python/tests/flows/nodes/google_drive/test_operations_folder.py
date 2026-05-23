from __future__ import annotations

from typing import Any

import analytiq_data as ad
import pytest

from analytiq_data.flows.nodes.google_drive.operations import execute_google_drive_item


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "params", "method", "path"),
    [
        ("create", {"name": "Projects", "folderId": "root"}, "POST", "/drive/v3/files"),
        ("deleteFolder", {"folderNoRootId": "folder-1", "options": {}}, "PATCH", "/drive/v3/files/folder-1"),
        (
            "deleteFolder",
            {"folderNoRootId": "folder-1", "options": {"deletePermanently": True}},
            "DELETE",
            "/drive/v3/files/folder-1",
        ),
        (
            "share",
            {
                "folderNoRootId": "folder-1",
                "permissionsUi": {
                    "permissionsValues": [
                        {"role": "writer", "type": "user", "emailAddress": "b@example.com"},
                    ]
                },
            },
            "POST",
            "/drive/v3/files/folder-1/permissions",
        ),
    ],
)
async def test_folder_operations_call_expected_api(
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
    mock_gd_api.return_value = {"id": "folder-1"}
    merged = {"resource": "folder", "operation": operation, **params}
    out = await execute_google_drive_item(drive_ctx, drive_node_shell, merged, drive_item, item_index=0)
    assert isinstance(out, ad.flows.FlowItem)
    mock_gd_api.assert_awaited()
    assert mock_gd_api.await_args.args[1] == method
    assert mock_gd_api.await_args.args[2] == path
    if operation == "create":
        body = mock_gd_api.await_args.kwargs.get("body") or mock_gd_api.await_args.args[3]
        assert body["mimeType"] == "application/vnd.google-apps.folder"
