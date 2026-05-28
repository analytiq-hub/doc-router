from __future__ import annotations

from analytiq_data.flows.integrations.microsoft import (
    MicrosoftGraphApiError,
    format_graph_user_error,
    graph_user_hint,
    normalize_drive_item_id,
)
from analytiq_data.flows.integrations.microsoft.graph_api import (
    _graph_error_message_from_body,
)


def test_graph_error_message_from_json_body() -> None:
    body = '{"error":{"code":"BadRequest","message":"Tenant does not have a SPO license."}}'
    assert _graph_error_message_from_body(body) == "Tenant does not have a SPO license."


def test_graph_user_hint_spo_license() -> None:
    assert graph_user_hint("Tenant does not have a SPO license.") is not None


def test_format_graph_user_error_prefers_hint() -> None:
    exc = MicrosoftGraphApiError(
        "raw",
        graph_message="Tenant does not have a SPO license.",
    )
    msg = format_graph_user_error(exc)
    assert "SharePoint Online" in msg


def test_normalize_drive_item_id_from_url() -> None:
    url = "https://onedrive.live.com/?id=ABC%21123&cid=xyz"
    assert normalize_drive_item_id(url) == "ABC!123"
