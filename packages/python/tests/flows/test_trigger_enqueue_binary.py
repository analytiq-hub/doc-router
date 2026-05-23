"""Tests for poll/schedule trigger enqueue binary preservation."""

from __future__ import annotations

import pytest

import analytiq_data as ad

from analytiq_data.flows.triggers.enqueue import serialize_flow_items_for_trigger


@pytest.mark.asyncio
async def test_serialize_flow_items_for_trigger_offloads_binary(monkeypatch) -> None:
    saved: list[dict] = []

    async def _fake_save(_client, *, bucket, key, blob, metadata=None):
        saved.append({"bucket": bucket, "key": key, "blob": blob, "metadata": metadata})

    monkeypatch.setattr(ad.mongodb.blob, "save_blob_async", _fake_save)

    items = [
        [
            ad.flows.FlowItem(
                json={"id": "m1"},
                binary={
                    "attachment_0": ad.flows.BinaryRef(
                        mime_type="application/pdf",
                        file_name="a.pdf",
                        data=b"%PDF",
                    ),
                    "attachment_1": ad.flows.BinaryRef(
                        mime_type="image/png",
                        file_name="b.png",
                        data=b"\x89PNG",
                    ),
                },
                meta={},
            )
        ]
    ]

    out = await serialize_flow_items_for_trigger(
        items,
        execution_id="exec1",
        trigger_node_id="trig1",
        analytiq_client=object(),
    )

    assert len(saved) == 2
    assert out[0][0]["binary"]["attachment_0"]["storage_id"] == (
        "flow_blobs:exec1/trigger/trig1/0/0/attachment_0"
    )
    assert out[0][0]["binary"]["attachment_1"]["file_name"] == "b.png"
    assert "data" not in out[0][0]["binary"]["attachment_0"]
