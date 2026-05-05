"""Tests for ``ad.flows.get_binary_stream`` (BinaryRef → bytes)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad


@pytest.mark.asyncio
async def test_get_binary_stream_uses_inline_data() -> None:
    ref = ad.flows.BinaryRef(mime_type="text/plain", data=b"hello")
    out = await ad.flows.get_binary_stream(ref, object())
    assert out == b"hello"


@pytest.mark.asyncio
async def test_get_binary_stream_loads_from_gridfs() -> None:
    ref = ad.flows.BinaryRef(mime_type="application/pdf", storage_id="files:abc.pdf")

    async def _fake_get(_client, *, bucket: str, key: str):
        assert bucket == "files"
        assert key == "abc.pdf"
        return {"blob": b"%PDF-1.4", "metadata": {}}

    with patch("analytiq_data.mongodb.blob.get_blob_async", new=AsyncMock(side_effect=_fake_get)):
        out = await ad.flows.get_binary_stream(ref, object())
    assert out == b"%PDF-1.4"


@pytest.mark.asyncio
async def test_get_binary_stream_invalid_storage_id() -> None:
    ref = ad.flows.BinaryRef(mime_type="text/plain", storage_id="no-colon")
    with pytest.raises(ValueError, match="Invalid"):
        await ad.flows.get_binary_stream(ref, object())
