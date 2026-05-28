from __future__ import annotations

import base64
from email.message import EmailMessage

import analytiq_data as ad

from analytiq_data.flows.nodes.gmail.email_parse import (
    decode_gmail_raw,
    parse_gmail_api_message,
    parse_raw_email_bytes,
)


def _encode_sample_raw(*, with_attachment: bool = False) -> str:
    msg = EmailMessage()
    msg["From"] = "sender@example.com"
    msg["To"] = "to@example.com"
    msg["Subject"] = "Hello"
    msg.set_content("Plain body")
    if with_attachment:
        msg.add_attachment(b"file-bytes", maintype="application", subtype="octet-stream", filename="doc.bin")
    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    return encoded.rstrip("=")


def test_decode_gmail_raw_round_trip() -> None:
    raw = _encode_sample_raw()
    data = decode_gmail_raw(raw)
    assert b"Plain body" in data


def test_parse_raw_email_bytes_extracts_text() -> None:
    parsed, binary = parse_raw_email_bytes(decode_gmail_raw(_encode_sample_raw()))
    assert parsed["subject"] == "Hello"
    assert parsed["text"] == "Plain body"
    assert binary == {}


def test_parse_gmail_api_message_downloads_attachment() -> None:
    raw = _encode_sample_raw(with_attachment=True)
    parsed, binary = parse_gmail_api_message(
        {"id": "m1", "threadId": "t1", "raw": raw},
        download_attachments=True,
        attachment_prefix="att_",
    )
    assert parsed["id"] == "m1"
    assert "att_0" in binary
    ref = binary["att_0"]
    assert isinstance(ref, ad.flows.BinaryRef)
    assert ref.file_name == "doc.bin"
    assert ref.data == b"file-bytes"
