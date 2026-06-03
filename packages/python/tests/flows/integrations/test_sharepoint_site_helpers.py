from __future__ import annotations

import pytest

from analytiq_data.flows.integrations.microsoft.site_helpers import (
    sharepoint_rest_api_base,
    sharepoint_tenant_rest_api_base,
    site_drive_delta_latest,
)


def test_sharepoint_tenant_rest_api_base() -> None:
    assert (
        sharepoint_tenant_rest_api_base("contoso")
        == "https://contoso.sharepoint.com/_api/v2.0"
    )


def test_sharepoint_rest_api_base_root() -> None:
    assert (
        sharepoint_rest_api_base("contoso", "root")
        == "https://contoso.sharepoint.com/_api/v2.0/sites/root"
    )


def test_sharepoint_rest_api_base_site_path() -> None:
    assert sharepoint_rest_api_base("contoso", "/sites/Team") == (
        "https://contoso.sharepoint.com/sites/Team/_api/v2.0"
    )


def test_sharepoint_rest_api_base_composite_host() -> None:
    assert sharepoint_rest_api_base(
        "contoso",
        "contoso.sharepoint.com:/sites/Team",
    ) == ("https://contoso.sharepoint.com/sites/Team/_api/v2.0")


def test_sharepoint_rest_api_base_requires_subdomain() -> None:
    with pytest.raises(RuntimeError, match="subdomain"):
        sharepoint_rest_api_base("", "root")


def test_site_drive_delta_latest_uses_rest_base() -> None:
    base = sharepoint_rest_api_base("contoso", "root")
    assert site_drive_delta_latest(base).endswith("/drive/root/delta?token=latest")
    assert "sharepoint.com/_api/v2.0" in site_drive_delta_latest(base)
