from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad

from analytiq_data.flows.nodes.microsoft_outlook.attachments import (
    download_message_attachments,
    resolve_outlook_download_attachments,
)
from analytiq_data.flows.nodes.microsoft_outlook.helpers import message_resource_path

_ATTACH = "analytiq_data.flows.nodes.microsoft_outlook.attachments"


def test_resolve_download_by_output_mode() -> None:
    assert resolve_outlook_download_attachments({"output": "simple"}) is False
    assert resolve_outlook_download_attachments({"output": "raw"}) is True
    assert resolve_outlook_download_attachments(
        {"output": "raw", "downloadAttachments": False}
    ) is True
    assert resolve_outlook_download_attachments({"output": "fields"}) is False
    assert resolve_outlook_download_attachments(
        {"output": "fields", "downloadAttachments": True}
    ) is True


def test_message_resource_path_encodes_equals() -> None:
    mid = "abc=def"
    assert message_resource_path(mid, "/attachments").endswith("/abc%3Ddef/attachments")


@pytest.mark.asyncio
async def test_download_message_attachments_uses_content_bytes() -> None:
    import base64

    ctx = ad.flows.ExecutionContext(
        execution_id="x",
        flow_id="f",
        flow_revid="r",
        organization_id="org",
        mode="manual",
        trigger_data={},
        run_data={},
        revision_nodes=[],
        credentials={},
        analytiq_client=None,
    )
    payload = b"hello"
    with patch(
        f"{_ATTACH}.outlook_request_all_items",
        new_callable=AsyncMock,
        return_value=[
            {
                "id": "a1",
                "name": "file.txt",
                "contentType": "text/plain",
                "contentBytes": base64.b64encode(payload).decode("ascii"),
            }
        ],
    ):
        out = await download_message_attachments(
            ctx,
            "tok",
            "https://graph.microsoft.com/v1.0/me",
            {"id": "m1", "hasAttachments": True},
        )
    assert out["attachment_0"].data == payload
