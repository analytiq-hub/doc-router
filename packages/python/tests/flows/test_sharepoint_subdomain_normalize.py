from __future__ import annotations

from analytiq_data.flows.credential_runtime import normalize_sharepoint_subdomain


def test_normalize_sharepoint_subdomain_slug() -> None:
    assert normalize_sharepoint_subdomain("contoso") == "contoso"


def test_normalize_sharepoint_subdomain_full_host() -> None:
    assert normalize_sharepoint_subdomain("contoso.sharepoint.com") == "contoso"


def test_normalize_sharepoint_subdomain_https_url() -> None:
    assert (
        normalize_sharepoint_subdomain("https://contoso.sharepoint.com/sites/Team")
        == "contoso"
    )
