import pytest

import analytiq_data as ad
from analytiq_data.system import settings as system_settings_mod
from analytiq_data.system.worker_counts import WorkerCounts, default_worker_counts
from tests.conftest_utils import client, get_auth_headers


def test_clamp_textract_max_concurrent():
    assert system_settings_mod.clamp_textract_max_concurrent(32) == 32
    assert system_settings_mod.clamp_textract_max_concurrent(0) == 0
    assert system_settings_mod.clamp_textract_max_concurrent(999) == 999
    assert system_settings_mod.clamp_textract_max_concurrent(2000) == 1024
    assert system_settings_mod.clamp_textract_max_concurrent(-5) == 0


def test_default_worker_counts_use_legacy_env(monkeypatch):
    monkeypatch.setenv("N_DOCROUTER_WORKERS", "7")
    counts = default_worker_counts()
    assert counts == WorkerCounts(
        n_ocr_workers=7,
        n_llm_workers=7,
        n_kb_index_workers=7,
        n_webhook_workers=7,
        n_flow_run_workers=7,
    )


@pytest.mark.asyncio
async def test_get_textract_max_concurrent_refreshes_every_25_requests(monkeypatch, test_db):
    system_settings_mod.invalidate_textract_max_concurrent_cache()
    system_settings_mod._cached_textract_max_concurrent = None
    system_settings_mod._textract_requests_since_refresh = 0

    await test_db.system_settings.update_one(
        {"_id": system_settings_mod.SYSTEM_SETTINGS_ID},
        {"$set": {"textract_max_concurrent": 10}},
        upsert=True,
    )

    load_calls = 0
    original_load = system_settings_mod.load_textract_max_concurrent_from_db

    async def counting_load():
        nonlocal load_calls
        load_calls += 1
        return await original_load()

    monkeypatch.setattr(
        system_settings_mod,
        "load_textract_max_concurrent_from_db",
        counting_load,
    )

    value = await system_settings_mod.get_textract_max_concurrent()
    assert value == 10
    assert load_calls == 1

    for _ in range(25):
        value = await system_settings_mod.get_textract_max_concurrent()
        assert value == 10
    assert load_calls == 1

    value = await system_settings_mod.get_textract_max_concurrent()
    assert value == 10
    assert load_calls == 2


@pytest.mark.asyncio
async def test_update_system_settings_invalidates_cache(test_db):
    system_settings_mod._cached_textract_max_concurrent = 5
    system_settings_mod._textract_requests_since_refresh = 0
    system_settings_mod._cached_worker_counts = WorkerCounts()
    system_settings_mod._worker_counts_requests_since_refresh = 0

    await system_settings_mod.update_system_settings(
        textract_max_concurrent=20,
        n_ocr_workers=3,
    )

    assert system_settings_mod._textract_requests_since_refresh == (
        system_settings_mod.TEXTRACT_MAX_CONCURRENT_REFRESH_EVERY
    )
    assert system_settings_mod._worker_counts_requests_since_refresh == (
        system_settings_mod.WORKER_COUNTS_REFRESH_EVERY
    )

    doc = await test_db.system_settings.find_one({"_id": system_settings_mod.SYSTEM_SETTINGS_ID})
    assert doc is not None
    assert doc["textract_max_concurrent"] == 20
    assert doc["n_ocr_workers"] == 3


@pytest.mark.asyncio
async def test_system_settings_api_get_and_patch(test_db, mock_auth):
    response = client.get("/v0/account/system_settings", headers=get_auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["textract_max_concurrent"] is not None
    assert body["n_ocr_workers"] is not None
    assert 0 <= body["textract_max_concurrent"] <= 1024
    assert 0 <= body["n_ocr_workers"] <= 256

    response = client.patch(
        "/v0/account/system_settings",
        headers=get_auth_headers(),
        json={"textract_max_concurrent": 16, "n_llm_workers": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["textract_max_concurrent"] == 16
    assert body["n_llm_workers"] == 5

    system_settings_mod.invalidate_system_settings_cache()
    counts = await ad.system.settings.get_worker_counts()
    assert counts.n_llm_workers == 5
