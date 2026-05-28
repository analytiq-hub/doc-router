from __future__ import annotations

import analytiq_data as ad


def test_google_drive_node_registration() -> None:
    ad.flows.register_builtin_nodes()
    nt = ad.flows.get("flows.google_drive")
    assert nt is not None
    assert getattr(nt, "experimental", False) is False
    assert nt.type_version == 3
    assert nt.icon_key == "google_drive"
    assert nt.palette_group == "app"
    slots = nt.credential_slots or []
    assert len(slots) == 1
    assert slots[0]["slot"] == "googleDriveOAuth2Api"
    assert slots[0]["required"] is True
