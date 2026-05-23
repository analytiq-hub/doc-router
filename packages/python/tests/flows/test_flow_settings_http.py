"""HTTP and cross-runtime tests for flow settings (timezone)."""

from __future__ import annotations

import json
import shutil
import subprocess
from zoneinfo import ZoneInfo

import pytest

import analytiq_data as ad
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


def _std_manual_node() -> dict:
    return {
        "id": "t1",
        "name": "Start",
        "type": "flows.trigger.manual",
        "position": [0, 0],
        "parameters": {},
        "webhook_id": None,
        "disabled": False,
        "on_error": "stop",
        "retry_on_fail": False,
        "max_tries": 1,
        "wait_between_tries_ms": 1000,
        "notes": None,
    }


def _intl_supported_timezones() -> list[str]:
    """Same source as the frontend picker: ``Intl.supportedValuesOf('timeZone')``."""

    if not shutil.which("node"):
        pytest.skip("node required to read Intl.supportedValuesOf('timeZone')")
    proc = subprocess.run(
        ["node", "-e", "console.log(JSON.stringify(Intl.supportedValuesOf('timeZone')))"],
        capture_output=True,
        text=True,
        check=True,
    )
    zones = json.loads(proc.stdout.strip())
    if not isinstance(zones, list) or not zones:
        pytest.skip("Intl.supportedValuesOf('timeZone') returned no zones")
    return [str(z) for z in zones]


def _browser_timezone() -> str:
    proc = subprocess.run(
        [
            "node",
            "-e",
            "console.log(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC')",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip() or "UTC"


def _frontend_flow_timezone_for_persist(draft: str, browser_tz: str) -> str:
    """Mirror ``flowTimezoneForPersist`` in ``flowTimezone.ts``."""

    token = draft.strip()
    if not token or token == "DEFAULT":
        return browser_tz.strip() or "UTC"
    return token


def test_intl_supported_timezones_pass_backend_validator() -> None:
    """Every browser-listed IANA zone must pass Python ``zoneinfo`` validation."""

    failures: list[str] = []
    for tz in _intl_supported_timezones():
        if ad.flows.validate_flow_settings({"timezone": tz}):
            failures.append(tz)
    assert failures == []


@pytest.mark.asyncio
async def test_put_flow_revision_accepts_intl_timezones(test_db, mock_auth) -> None:
    """POST/PUT a revision using timezones from ``Intl.supportedValuesOf``."""

    intl_zones = _intl_supported_timezones()
    browser_tz = _browser_timezone()
    sample = list(dict.fromkeys([browser_tz, "UTC", intl_zones[0], intl_zones[-1], "Europe/Berlin"]))

    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={
            "name": "Timezone settings",
            "nodes": [_std_manual_node()],
            "connections": {},
            "settings": {"timezone": sample[0]},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]
    base_revid = r0.json()["revision"]["flow_revid"]

    try:
        for i, tz in enumerate(sample):
            r1 = client.put(
                f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
                json={
                    "base_flow_revid": base_revid,
                    "name": "Timezone settings",
                    "nodes": [_std_manual_node()],
                    "connections": {},
                    "settings": {"timezone": tz},
                    "pin_data": None,
                },
                headers=get_auth_headers(),
            )
            assert r1.status_code == 200, f"timezone={tz!r} body={r1.text}"
            rev = r1.json().get("revision")
            if i == 0 and tz == sample[0]:
                assert rev is None
                continue
            assert rev is not None, f"expected new revision for timezone {tz!r}"
            assert rev["settings"].get("timezone") == tz
            base_revid = rev["flow_revid"]
    finally:
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}", headers=get_auth_headers())


@pytest.mark.asyncio
async def test_timezone_frontend_persist_round_trips_via_http(test_db, mock_auth) -> None:
    """Frontend DEFAULT/IANA → persisted IANA → ``zoneinfo`` → stored → GET revision."""

    browser_tz = _browser_timezone()
    cases = [
        ("DEFAULT", _frontend_flow_timezone_for_persist("DEFAULT", browser_tz)),
        ("Europe/Berlin", "Europe/Berlin"),
    ]

    r0 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={
            "name": "Timezone round-trip",
            "nodes": [_std_manual_node()],
            "connections": {},
            "settings": {"timezone": cases[0][1]},
            "pin_data": None,
        },
        headers=get_auth_headers(),
    )
    assert r0.status_code == 200, r0.text
    flow_id = r0.json()["flow"]["flow_id"]
    base_revid = r0.json()["revision"]["flow_revid"]

    try:
        for i, (_draft, persisted_tz) in enumerate(cases):
            assert ad.flows.validate_flow_settings({"timezone": persisted_tz}) == []
            ZoneInfo(ad.flows.resolve_flow_timezone({"timezone": persisted_tz}))

            if i == 0:
                stored_revid = base_revid
            else:
                r1 = client.put(
                    f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
                    json={
                        "base_flow_revid": base_revid,
                        "name": "Timezone round-trip",
                        "nodes": [_std_manual_node()],
                        "connections": {},
                        "settings": {"timezone": persisted_tz},
                        "pin_data": None,
                    },
                    headers=get_auth_headers(),
                )
                assert r1.status_code == 200, r1.text
                rev = r1.json().get("revision")
                assert rev is not None
                stored_revid = rev["flow_revid"]
                base_revid = stored_revid

            r_get = client.get(
                f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}/revisions/{stored_revid}",
                headers=get_auth_headers(),
            )
            assert r_get.status_code == 200, r_get.text
            assert r_get.json()["settings"].get("timezone") == persisted_tz
    finally:
        client.delete(f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}", headers=get_auth_headers())
