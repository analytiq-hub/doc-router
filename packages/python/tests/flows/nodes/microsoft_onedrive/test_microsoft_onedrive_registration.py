from __future__ import annotations

import analytiq_data as ad


def test_microsoft_onedrive_node_registration() -> None:
    ad.flows.register_builtin_nodes()
    nt = ad.flows.get("flows.microsoft_onedrive")
    assert nt is not None
    assert nt.label == "Microsoft OneDrive"
    assert nt.description == "Consume Microsoft OneDrive API"
    assert getattr(nt, "experimental", False) is True
    assert nt.type_version == 1
    assert nt.icon_key == "microsoft_onedrive"
    slots = nt.credential_slots or []
    assert len(slots) == 1
    assert slots[0]["slot"] == "microsoftOneDriveOAuth2Api"
    assert slots[0]["required"] is True
