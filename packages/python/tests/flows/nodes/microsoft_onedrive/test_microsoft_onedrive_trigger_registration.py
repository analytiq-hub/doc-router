from __future__ import annotations

import analytiq_data as ad


def test_microsoft_onedrive_trigger_registration() -> None:
    ad.flows.register_builtin_nodes()
    nt = ad.flows.get("flows.trigger.microsoft_onedrive")
    assert nt is not None
    assert nt.label == "Microsoft OneDrive Trigger"
    assert nt.description == "Trigger for Microsoft OneDrive API."
    assert getattr(nt, "experimental", False) is True
    assert getattr(nt, "polling", False) is True
    assert nt.is_trigger is True
    assert nt.icon_key == "microsoft_onedrive"
    slots = nt.credential_slots or []
    assert len(slots) == 1
    assert slots[0]["slot"] == "microsoftOneDriveOAuth2Api"
