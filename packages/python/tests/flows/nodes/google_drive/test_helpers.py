from __future__ import annotations

import pytest

from analytiq_data.flows.nodes.google_drive.helpers import (
    drive_file_id_from_param,
    export_fallback_mimes,
    export_mime_for_google_app,
    permissions_from_ui,
    prepare_query_fields,
    rlc_value,
    set_parent_folder,
    validate_resource_operation,
)


def test_drive_file_id_from_docs_url() -> None:
    url = "https://docs.google.com/document/d/1QLUu--7KcnD5HNeY7NaOhtSQV-EH8US7UrtNkM7zigA/edit"
    assert drive_file_id_from_param(url) == "1QLUu--7KcnD5HNeY7NaOhtSQV-EH8US7UrtNkM7zigA"


def test_drive_file_id_plain_id() -> None:
    assert drive_file_id_from_param("abc123XYZ") == "abc123XYZ"


def test_rlc_value_accepts_json_resource_locator() -> None:
    raw = '{"mode":"id","value":"folder-99"}'
    assert rlc_value(raw) == "folder-99"


def test_set_parent_folder_prefers_explicit_folder() -> None:
    assert set_parent_folder("folder-a", "drive-b") == "folder-a"
    assert set_parent_folder("root", "shared-drive-1") == "shared-drive-1"
    assert set_parent_folder("root", "My Drive") == "root"


def test_export_mime_defaults_match_n8n_v2() -> None:
    doc_mime = "application/vnd.google-apps.document"
    assert (
        export_mime_for_google_app(doc_mime, {})
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    sheet_mime = "application/vnd.google-apps.spreadsheet"
    assert export_mime_for_google_app(sheet_mime, {}) == "text/csv"
    assert (
        export_mime_for_google_app(
            doc_mime,
            {"googleFileConversion": {"conversion": {"docsToFormat": "text/plain"}}},
        )
        == "text/plain"
    )


def test_export_fallback_mimes_skips_primary() -> None:
    doc_mime = "application/vnd.google-apps.document"
    primary = export_mime_for_google_app(doc_mime, {})
    fallbacks = export_fallback_mimes(doc_mime, primary)
    assert primary not in fallbacks
    assert "text/html" in fallbacks


def test_prepare_query_fields() -> None:
    assert prepare_query_fields(["id", "name"]) == "id, name"
    assert prepare_query_fields(["*"]) == "*"
    assert prepare_query_fields(None) == "id, name"


def test_permissions_from_ui() -> None:
    rows = permissions_from_ui(
        {
            "permissionsValues": [
                {"role": "reader", "type": "user", "emailAddress": "a@example.com"},
            ]
        }
    )
    assert rows == [{"role": "reader", "type": "user", "emailAddress": "a@example.com"}]


def test_validate_resource_operation_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown Google Drive resource/operation"):
        validate_resource_operation("file", "notAnOp")
