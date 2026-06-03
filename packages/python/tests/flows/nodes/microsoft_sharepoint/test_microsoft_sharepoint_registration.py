from __future__ import annotations

import analytiq_data as ad


def test_microsoft_sharepoint_node_registration() -> None:
    ad.flows.register_builtin_nodes()
    nt = ad.flows.get("flows.microsoft_sharepoint")
    assert nt is not None
    assert nt.label == "Microsoft SharePoint"
    assert nt.description == "Consume Microsoft SharePoint API"
    assert getattr(nt, "experimental", False) is True
    assert nt.type_version == 1
    assert nt.icon_key == "microsoft_sharepoint"
    slots = nt.credential_slots or []
    assert len(slots) == 1
    assert slots[0]["slot"] == "microsoftSharePointOAuth2Api"
    assert slots[0]["required"] is True


def test_microsoft_sharepoint_trigger_registration() -> None:
    ad.flows.register_builtin_nodes()
    nt = ad.flows.get("flows.trigger.microsoft_sharepoint")
    assert nt is not None
    assert nt.label == "Microsoft SharePoint Trigger"
    assert getattr(nt, "polling", False) is True
    assert nt.icon_key == "microsoft_sharepoint"
