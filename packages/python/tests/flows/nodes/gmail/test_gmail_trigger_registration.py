from __future__ import annotations

import analytiq_data as ad


def test_gmail_trigger_registration() -> None:
    ad.flows.register_builtin_nodes()
    nt = ad.flows.get("flows.trigger.gmail")
    assert nt is not None
    assert getattr(nt, "experimental", False) is False
    assert getattr(nt, "polling", False) is True
    assert nt.is_trigger is True
    assert nt.palette_group == "trigger"
    assert nt.icon_key == "gmail"
    slots = nt.credential_slots or []
    assert len(slots) == 1
    assert slots[0]["slot"] == "gmailOAuth2"
