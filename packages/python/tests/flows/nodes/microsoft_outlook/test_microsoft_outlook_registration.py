"""Registration smoke tests for ``flows.microsoft_outlook``."""


def test_microsoft_outlook_node_registration() -> None:
    import analytiq_data as ad

    nt = ad.flows.get("flows.microsoft_outlook")
    assert nt.label == "Microsoft Outlook"
    assert nt.experimental is True
    assert nt.credential_slots[0]["slot"] == "microsoftOutlookOAuth2Api"
    props = (nt.parameter_schema or {}).get("properties") or {}
    assert "message" in (props.get("resource") or {}).get("enum", [])
