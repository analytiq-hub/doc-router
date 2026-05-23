from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import analytiq_data as ad
import pytest

from analytiq_data.flows.nodes.google_drive.operations import _file_download, execute_google_drive_item


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "params", "method", "path", "side_effect"),
    [
        (
            "copy",
            {"fileId": "f1", "name": "Copy of doc", "sameFolder": False, "folderId": "folder-1"},
            "POST",
            "/drive/v3/files/f1/copy",
            None,
        ),
        (
            "deleteFile",
            {"fileId": "f1", "options": {}},
            "PATCH",
            "/drive/v3/files/f1",
            None,
        ),
        (
            "deleteFile",
            {"fileId": "f1", "options": {"deletePermanently": True}},
            "DELETE",
            "/drive/v3/files/f1",
            None,
        ),
        (
            "move",
            {"fileId": "f1", "folderId": "dest-folder"},
            "PATCH",
            "/drive/v3/files/f1",
            [{"parents": ["old-parent"]}, {"id": "f1"}],
        ),
        (
            "share",
            {
                "fileId": "f1",
                "permissionsUi": {
                    "permissionsValues": [
                        {"role": "reader", "type": "user", "emailAddress": "a@example.com"},
                    ]
                },
            },
            "POST",
            "/drive/v3/files/f1/permissions",
            None,
        ),
        (
            "createFromText",
            {"name": "notes.txt", "content": "hello", "folderId": "root"},
            "POST",
            "/upload/drive/v3/files",
            None,
        ),
        (
            "update",
            {"fileId": "f1", "newUpdatedFileName": "renamed.pdf", "changeFileContent": False},
            "PATCH",
            "/drive/v3/files/f1",
            None,
        ),
    ],
)
async def test_file_operations_call_expected_api(
    drive_ctx: ad.flows.ExecutionContext,
    drive_item: ad.flows.FlowItem,
    drive_node_shell: dict[str, Any],
    mock_oauth_token,
    mock_gd_api,
    operation: str,
    params: dict[str, Any],
    method: str,
    path: str,
    side_effect: list[Any] | None,
) -> None:
    if side_effect is not None:
        mock_gd_api.side_effect = side_effect
    else:
        mock_gd_api.return_value = {"id": "f1"}

    upload_patch = patch(
        "analytiq_data.flows.nodes.google_drive.operations.upload_multipart_file",
        new_callable=AsyncMock,
        return_value={"id": "uploaded-1"},
    )
    with upload_patch:
        merged = {"resource": "file", "operation": operation, **params}
        out = await execute_google_drive_item(drive_ctx, drive_node_shell, merged, drive_item, item_index=0)
    assert isinstance(out, ad.flows.FlowItem)
    mock_gd_api.assert_awaited()
    if operation == "createFromText":
        return
    if operation == "deleteFile" and params.get("options", {}).get("deletePermanently"):
        assert mock_gd_api.await_args.args[1] == "DELETE"
    elif operation == "move":
        assert mock_gd_api.await_args.args[1] == "PATCH"
    else:
        assert mock_gd_api.await_args.args[1] == method
    assert path in mock_gd_api.await_args.args[2]


@pytest.mark.asyncio
async def test_file_download_preserves_meta(
    drive_item: ad.flows.FlowItem,
    mock_gd_api,
) -> None:
    mock_gd_api.side_effect = [
        {"mimeType": "application/pdf", "name": "report.pdf"},
        b"%PDF-1.4",
    ]
    out = await _file_download(
        context=None,  # type: ignore[arg-type]
        token="tok",
        file_id="fid",
        params={},
        item=drive_item,
        options={},
    )
    assert out.meta == {"trace": "t1"}
    assert "data" in out.binary
    assert out.binary["data"].mime_type == "application/pdf"


@pytest.mark.asyncio
async def test_file_upload_uses_multipart_for_small_binary(
    drive_ctx: ad.flows.ExecutionContext,
    drive_node_shell: dict[str, Any],
    mock_oauth_token,
    mock_gd_api,
) -> None:
    item = ad.flows.FlowItem(
        json={},
        binary={
            "data": ad.flows.BinaryRef(
                mime_type="text/plain",
                file_name="hello.txt",
                data=b"hello",
            )
        },
        meta={},
    )
    mock_gd_api.return_value = {"id": "patched-1", "name": "hello.txt"}
    with patch(
        "analytiq_data.flows.nodes.google_drive.operations.upload_multipart_file",
        new_callable=AsyncMock,
        return_value={"id": "uploaded-1"},
    ) as upload_mock:
        params = {
            "resource": "file",
            "operation": "upload",
            "name": "hello.txt",
            "inputDataFieldName": "data",
        }
        out = await execute_google_drive_item(drive_ctx, drive_node_shell, params, item, item_index=0)
    upload_mock.assert_awaited_once()
    assert out.json["id"] == "patched-1"
    assert mock_gd_api.await_args.args[1] == "PATCH"
    assert mock_gd_api.await_args.args[2] == "/drive/v3/files/uploaded-1"
