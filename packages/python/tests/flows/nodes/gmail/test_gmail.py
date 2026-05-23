from __future__ import annotations

import analytiq_data as ad
import pytest

from analytiq_data.flows.nodes.gmail.helpers import (
    prepare_emails_input,
    prepare_gmail_list_query,
    validate_resource_operation,
)


def test_validate_resource_operation_accepts_all_resources() -> None:
    validate_resource_operation("message", "send")
    validate_resource_operation("label", "getAll")
    validate_resource_operation("draft", "create")
    validate_resource_operation("thread", "trash")
    with pytest.raises(ValueError, match="resource"):
        validate_resource_operation("mailbox", "getAll")


def test_prepare_emails_input_formats_addresses() -> None:
    assert prepare_emails_input("a@example.com, b@example.com", "To") == (
        "<a@example.com>, <b@example.com>"
    )


def test_prepare_gmail_list_query_builds_q() -> None:
    qs = prepare_gmail_list_query(
        {"q": "has:attachment", "sender": "boss@corp.com", "readStatus": "unread"}
    )
    assert "has:attachment" in qs["q"]
    assert "from:boss@corp.com" in qs["q"]
    assert "is:unread" in qs["q"]


def test_gmail_node_registered() -> None:
    ad.flows.register_builtin_nodes()
    nt = ad.flows.get("flows.gmail")
    assert nt is not None
    assert nt.label == "Gmail"
    assert nt.icon_key == "gmail"
    assert nt.credential_slots[0]["slot"] == "gmailOAuth2"
