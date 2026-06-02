from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad

from analytiq_data.flows.nodes.microsoft_outlook.trigger import FlowsMicrosoftOutlookTriggerNode

_TRIGGER = "analytiq_data.flows.nodes.microsoft_outlook.trigger"


@pytest.mark.asyncio
async def test_manual_execute_polls_outlook() -> None:
    node_def = {
        "id": "ol1",
        "name": "Outlook",
        "type": "flows.trigger.microsoft_outlook",
        "parameters": {"output": "raw"},
    }
    ctx = ad.flows.ExecutionContext(
        execution_id="exec1",
        flow_id="flow1",
        flow_revid="rev1",
        organization_id="org1",
        mode="manual",
        trigger_data={"type": "manual"},
        run_data={},
        revision_nodes=[],
        credentials={},
        analytiq_client=None,
    )
    fake_items = [
        [
            ad.flows.FlowItem(
                json={"id": "m1", "subject": "Test"},
                binary={"attachment_0": ad.flows.BinaryRef(mime_type="text/plain", data=b"x")},
                meta={},
            )
        ]
    ]
    nt = FlowsMicrosoftOutlookTriggerNode()
    with patch(
        f"{_TRIGGER}.poll_microsoft_outlook_trigger",
        new_callable=AsyncMock,
        return_value=fake_items,
    ) as poll:
        out = await nt.execute(ctx, node_def, [])
    poll.assert_awaited_once()
    assert out[0][0].binary["attachment_0"].data == b"x"
