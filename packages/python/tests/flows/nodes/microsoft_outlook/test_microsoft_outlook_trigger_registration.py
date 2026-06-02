"""Registration smoke tests for ``flows.trigger.microsoft_outlook``."""


def test_microsoft_outlook_trigger_registration() -> None:
    import analytiq_data as ad

    nt = ad.flows.get("flows.trigger.microsoft_outlook")
    assert nt.label == "Microsoft Outlook Trigger"
    assert nt.polling is True
    assert nt.experimental is True
    assert nt.credential_slots[0]["slot"] == "microsoftOutlookOAuth2Api"
