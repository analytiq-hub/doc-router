from __future__ import annotations

from analytiq_data.flows.integrations.microsoft import (
    graph_site_base_url,
    normalize_site_id,
    site_drive_delta_latest,
)


def test_normalize_site_id_root() -> None:
    assert normalize_site_id("") == "root"
    assert normalize_site_id("root") == "root"


def test_normalize_site_id_from_url() -> None:
    assert (
        normalize_site_id("https://contoso.sharepoint.com/sites/Team")
        == "contoso.sharepoint.com:/sites/Team"
    )


def test_graph_site_base_url() -> None:
    assert graph_site_base_url("root") == "https://graph.microsoft.com/v1.0/sites/root"
    base = graph_site_base_url("contoso.sharepoint.com:/sites/Team")
    assert base.startswith("https://graph.microsoft.com/v1.0/sites/")
    assert "contoso.sharepoint.com" in base


def test_site_drive_delta_latest() -> None:
    base = graph_site_base_url("root")
    assert site_drive_delta_latest(base).endswith("/drive/root/delta?token=latest")
