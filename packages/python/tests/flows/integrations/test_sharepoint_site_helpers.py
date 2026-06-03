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


def test_sharepoint_rest_api_base_bare_site_slug() -> None:
    assert sharepoint_rest_api_base("docrouter", "GreenieRE") == (
        "https://docrouter.sharepoint.com/sites/GreenieRE/_api/v2.0"
    )


def test_normalize_site_id_bare_slug() -> None:
    from analytiq_data.flows.integrations.microsoft.site_helpers import normalize_site_id

    assert normalize_site_id("GreenieRE") == "/sites/GreenieRE"
    assert sharepoint_rest_api_base(
        "docrouter",
        "https://docrouter.sharepoint.com/sites/GreenieRE/SitePages/CollabHome.aspx",
    ) == ("https://docrouter.sharepoint.com/sites/GreenieRE/_api/v2.0")


def test_normalize_site_id_strips_site_pages_from_url() -> None:
    from analytiq_data.flows.integrations.microsoft.site_helpers import normalize_site_id

    assert normalize_site_id(
        "https://docrouter.sharepoint.com/sites/GreenieRE/SitePages/CollabHome.aspx"
    ) == "docrouter.sharepoint.com:/sites/GreenieRE"


def test_site_drive_delta_latest_uses_rest_base() -> None:
    base = sharepoint_rest_api_base("contoso", "root")
    assert site_drive_delta_latest(base).endswith("/drive/root/delta?token=latest")
    assert "sharepoint.com/_api/v2.0" in site_drive_delta_latest(base)
