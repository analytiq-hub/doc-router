from __future__ import annotations

import base64
from typing import Any

import pytest

import analytiq_data as ad
from analytiq_data.flows.code_runner.config import SecurityConfig
from analytiq_data.flows.code_runner.rpc import ParentRpcHandler


@pytest.fixture
def rpc_config() -> SecurityConfig:
    return SecurityConfig.from_env()


@pytest.mark.asyncio
async def test_parent_rpc_read_binary_returns_base64(monkeypatch, rpc_config: SecurityConfig) -> None:
    seen: dict[str, Any] = {}

    async def _fake_get(ref: ad.flows.BinaryRef, _client: Any) -> bytes:
        seen["storage_id"] = ref.storage_id
        return b"%PDF-1.4"

    monkeypatch.setattr(ad.flows, "get_binary_stream", _fake_get)

    handler = ParentRpcHandler(
        analytiq_client=object(),
        execution_id="exec1",
        node_id="c1",
        config=rpc_config,
    )
    result = await handler.handle("read_binary", ["files:doc.pdf"])

    assert seen["storage_id"] == "files:doc.pdf"
    assert base64.b64decode(result) == b"%PDF-1.4"


@pytest.mark.asyncio
async def test_parent_rpc_read_binary_rejects_invalid_storage_id(rpc_config: SecurityConfig) -> None:
    handler = ParentRpcHandler(
        analytiq_client=object(),
        execution_id="exec1",
        node_id="c1",
        config=rpc_config,
    )
    with pytest.raises(ValueError, match="Invalid storage_id"):
        await handler.handle("read_binary", ["no-bucket-prefix"])


@pytest.mark.asyncio
async def test_parent_rpc_read_binary_enforces_size_limit(monkeypatch) -> None:
    config = SecurityConfig.from_env()

    async def _fake_get(_ref: ad.flows.BinaryRef, _client: Any) -> bytes:
        return b"x" * (config.binary_read_max_bytes + 1)

    monkeypatch.setattr(ad.flows, "get_binary_stream", _fake_get)

    handler = ParentRpcHandler(
        analytiq_client=object(),
        execution_id="exec1",
        node_id="c1",
        config=config,
    )
    with pytest.raises(ValueError, match="exceeds read limit"):
        await handler.handle("read_binary", ["files:big.bin"])


@pytest.mark.asyncio
async def test_parent_rpc_store_binary_persists_and_returns_storage_id(
    monkeypatch, rpc_config: SecurityConfig
) -> None:
    saved: dict[str, Any] = {}

    async def _fake_save(_client: Any, **kwargs: Any) -> ad.flows.BinaryRef:
        saved.update(kwargs)
        return ad.flows.BinaryRef(
            mime_type=kwargs["mime_type"],
            file_name=kwargs["file_name"],
            storage_id=f"flow_blobs:{kwargs['execution_id']}/{kwargs['node_id']}/{kwargs['item_index']}/data",
        )

    monkeypatch.setattr(ad.flows, "save_execution_binary_blob", _fake_save)

    handler = ParentRpcHandler(
        analytiq_client=object(),
        execution_id="exec1",
        node_id="c1",
        config=rpc_config,
    )
    payload_b64 = base64.b64encode(b"hello").decode("ascii")
    sid = await handler.handle("store_binary", ["text/plain", "out.txt", payload_b64])

    assert sid == "flow_blobs:exec1/c1/0/data"
    assert saved["blob"] == b"hello"
    assert saved["mime_type"] == "text/plain"
    assert saved["file_name"] == "out.txt"
    assert saved["item_index"] == 0

    sid2 = await handler.handle("store_binary", ["text/plain", "out2.txt", payload_b64])
    assert saved["item_index"] == 1
    assert sid2 == "flow_blobs:exec1/c1/1/data"


@pytest.mark.asyncio
async def test_parent_rpc_store_binary_rejects_invalid_base64(rpc_config: SecurityConfig) -> None:
    handler = ParentRpcHandler(
        analytiq_client=object(),
        execution_id="exec1",
        node_id="c1",
        config=rpc_config,
    )
    with pytest.raises(ValueError, match="Invalid base64"):
        await handler.handle("store_binary", ["text/plain", "out.txt", "not!!!base64"])


@pytest.mark.asyncio
async def test_run_python_code_read_and_store_binary_roundtrip(monkeypatch) -> None:
    read_ids: list[str] = []

    async def _fake_get(ref: ad.flows.BinaryRef, _client: Any) -> bytes:
        read_ids.append(ref.storage_id or "")
        return b"roundtrip-bytes"

    async def _fake_save(_client: Any, **kwargs: Any) -> ad.flows.BinaryRef:
        return ad.flows.BinaryRef(
            mime_type=kwargs["mime_type"],
            file_name=kwargs["file_name"],
            storage_id="flow_blobs:exec/c1/0/data",
        )

    monkeypatch.setattr(ad.flows, "get_binary_stream", _fake_get)
    monkeypatch.setattr(ad.flows, "save_execution_binary_blob", _fake_save)

    code = """
import base64

def run(items, context):
    raw_b64 = read_binary("files:in/doc.bin")
    nbytes = len(base64.b64decode(raw_b64))
    sid = store_binary("application/octet-stream", "out.bin", raw_b64)
    return [{
        "json": {"nbytes": nbytes},
        "binary": {
            "doc": {
                "storage_id": sid,
                "mime_type": "application/octet-stream",
                "file_name": "out.bin",
            }
        },
    }]
"""
    out, _logs = await ad.flows.run_python_code(
        code=code,
        items=[{"json": {}, "binary": {}, "meta": {}}],
        context={},
        analytiq_client=object(),
        execution_id="exec",
        node_id="c1",
        timeout_seconds=5,
    )

    assert read_ids == ["files:in/doc.bin"]
    assert out[0]["json"]["nbytes"] == len(b"roundtrip-bytes")
    assert out[0]["binary"]["doc"]["storage_id"] == "flow_blobs:exec/c1/0/data"
