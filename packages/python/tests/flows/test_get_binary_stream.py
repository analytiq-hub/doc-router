"""Tests for ``ad.flows.get_binary_stream`` (BinaryRef → bytes), scoped to the run's organization."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

import analytiq_data as ad

ORG = "org-a"
EXEC_ID = "65f000000000000000000001"
REV_ID = "65f000000000000000000002"
FLOW_ID = "65f000000000000000000003"


class _Coll:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    async def find_one(self, query: dict[str, Any], _projection: Any = None):
        for doc in self._docs:
            if all(_match(doc, k, v) for k, v in query.items()):
                return doc
        return None


def _match(doc: dict[str, Any], key: str, value: Any) -> bool:
    if key == "$or":
        return any(all(_match(doc, k, v) for k, v in alt.items()) for alt in value)
    return doc.get(key) == value


class _FakeDb:
    def __init__(self) -> None:
        self.docs = _Coll([{"organization_id": ORG, "pdf_file_name": "mine.pdf", "mongo_file_name": "mine.docx"}])
        self.flow_executions = _Coll([{"_id": ObjectId(EXEC_ID), "organization_id": ORG}])
        self.flow_revisions = _Coll([{"_id": ObjectId(REV_ID), "flow_id": FLOW_ID}])
        self.flows = _Coll([{"_id": ObjectId(FLOW_ID), "organization_id": ORG}])


@pytest.fixture
def fake_db():
    db = _FakeDb()
    with patch("analytiq_data.common.get_async_db", return_value=db):
        yield db


@pytest.fixture
def fake_blob():
    async def _fake_get(_client, *, bucket: str, key: str):
        return {"blob": f"{bucket}:{key}".encode(), "metadata": {}}

    with patch("analytiq_data.mongodb.blob.get_blob_async", new=AsyncMock(side_effect=_fake_get)) as m:
        yield m


@pytest.mark.asyncio
async def test_get_binary_stream_uses_inline_data() -> None:
    ref = ad.flows.BinaryRef(mime_type="text/plain", data=b"hello")
    out = await ad.flows.get_binary_stream(ref, object(), organization_id=ORG)
    assert out == b"hello"


@pytest.mark.asyncio
async def test_get_binary_stream_invalid_storage_id() -> None:
    ref = ad.flows.BinaryRef(mime_type="text/plain", storage_id="no-colon")
    with pytest.raises(ValueError, match="Invalid"):
        await ad.flows.get_binary_stream(ref, object(), organization_id=ORG)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "storage_id",
    [
        "files:mine.pdf",
        "files:mine.docx",
        f"flow_blobs:{EXEC_ID}/node/0/data",
        f"flow_pins:pin/{REV_ID}/node/0/0/data/a.pdf",
    ],
)
async def test_get_binary_stream_reads_own_organization(fake_db, fake_blob, storage_id) -> None:
    ref = ad.flows.BinaryRef(mime_type="application/pdf", storage_id=storage_id)
    out = await ad.flows.get_binary_stream(ref, object(), organization_id=ORG)
    assert out == storage_id.encode()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "storage_id",
    [
        "files:theirs.pdf",
        "flow_blobs:65f0000000000000000000ff/node/0/data",
        "flow_blobs:not-an-object-id/node/0/data",
        "flow_pins:pin/65f0000000000000000000fe/node/0/0/data/a.pdf",
        "flow_pins:other/key",
        "fs:anything",
    ],
)
async def test_get_binary_stream_refuses_other_storage(fake_db, fake_blob, storage_id) -> None:
    ref = ad.flows.BinaryRef(mime_type="application/pdf", storage_id=storage_id)
    with pytest.raises(ad.flows.BinaryAccessError):
        await ad.flows.get_binary_stream(ref, object(), organization_id=ORG)
    fake_blob.assert_not_called()


@pytest.mark.asyncio
async def test_get_binary_stream_refuses_another_organization(fake_db, fake_blob) -> None:
    ref = ad.flows.BinaryRef(mime_type="application/pdf", storage_id="files:mine.pdf")
    with pytest.raises(ad.flows.BinaryAccessError):
        await ad.flows.get_binary_stream(ref, object(), organization_id="org-b")
    fake_blob.assert_not_called()
