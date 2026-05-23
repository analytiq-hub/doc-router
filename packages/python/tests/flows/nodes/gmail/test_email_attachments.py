from __future__ import annotations

import base64

import analytiq_data as ad
import pytest

from analytiq_data.flows.nodes.gmail.email_attachments import (
    OutboundAttachment,
    attachment_binary_property_names,
    resolve_outbound_attachments,
)
from analytiq_data.flows.nodes.gmail.email_mime import encode_email_raw
from analytiq_data.flows.nodes.gmail.email_parse import (
    decode_gmail_raw,
    parse_gmail_api_message,
    resolve_download_attachments,
)


def test_attachment_binary_property_names_supports_shorthand_and_n8n_shape() -> None:
    assert attachment_binary_property_names({"attachmentsBinary": ["data", "extra"]}) == [
        "data",
        "extra",
    ]
    assert attachment_binary_property_names(
        {"attachmentsUi": {"attachmentsBinary": [{"property": "report"}, {"property": "a,b"}]}}
    ) == ["report", "a", "b"]


@pytest.mark.asyncio
async def test_resolve_outbound_attachments_reads_item_binary() -> None:
    ctx = ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={},
        run_data={},
        analytiq_client=None,
    )
    item = ad.flows.FlowItem(
        json={},
        binary={
            "data": ad.flows.BinaryRef(
                mime_type="application/pdf",
                file_name="invoice.pdf",
                data=b"%PDF-1",
            )
        },
        meta={},
    )
    attachments = await resolve_outbound_attachments(
        ctx, item, {"attachmentsBinary": ["data"]}
    )
    assert len(attachments) == 1
    assert attachments[0].name == "invoice.pdf"
    assert attachments[0].content == b"%PDF-1"


def test_encode_email_raw_includes_attachment_bytes() -> None:
    raw = encode_email_raw(
        to="<a@example.com>",
        subject="Files",
        body_text="See attached",
        attachments=[
            OutboundAttachment(
                name="doc.bin",
                content=b"hello-bytes",
                mime_type="application/octet-stream",
            )
        ],
    )
    decoded = decode_gmail_raw(raw)
    assert b"hello-bytes" in decoded or b"aGVsbG8tYnl0ZXM=" in decoded
    assert b"doc.bin" in decoded


def test_resolve_download_attachments_defaults_true_when_not_simple() -> None:
    assert resolve_download_attachments({}, simple=False) is True
    assert resolve_download_attachments({"downloadAttachments": False}, simple=False) is False
    assert resolve_download_attachments({}, simple=True) is False


def test_parse_gmail_api_message_inline_attachment_with_filename() -> None:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = "Inline"
    msg.set_content("Body")
    msg.add_attachment(
        b"png-bytes",
        maintype="image",
        subtype="png",
        filename="scan.png",
        disposition="inline",
    )
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii").rstrip("=")
    _, binary = parse_gmail_api_message(
        {"id": "m1", "raw": raw},
        download_attachments=True,
        attachment_prefix="att_",
    )
    assert "att_0" in binary
    assert binary["att_0"].file_name == "scan.png"
    assert binary["att_0"].data == b"png-bytes"
