"""Tests for Outlook shared-mailbox Graph base URL helper."""

from analytiq_data.flows.integrations.microsoft import graph_mailbox_base_url, graph_url_for_path


def test_graph_mailbox_base_default_me() -> None:
    assert graph_mailbox_base_url({}) == "https://graph.microsoft.com/v1.0/me"


def test_graph_mailbox_base_shared() -> None:
    base = graph_mailbox_base_url(
        {"useShared": True, "userPrincipalName": "user@contoso.com"}
    )
    assert base == "https://graph.microsoft.com/v1.0/users/user%40contoso.com"


def test_graph_url_for_path() -> None:
    url = graph_url_for_path(
        "/messages",
        mailbox_base="https://graph.microsoft.com/v1.0/users/u@x.com",
    )
    assert url.endswith("/users/u@x.com/messages")
