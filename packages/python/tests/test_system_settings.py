import pytest

import analytiq_data as ad
from tests.conftest_utils import client, get_auth_headers


def test_clamp_textract_max_concurrent():
    assert ad.system.settings.clamp_textract_max_concurrent(32) == 32
    assert ad.system.settings.clamp_textract_max_concurrent(0) == 0
    assert ad.system.settings.clamp_textract_max_concurrent(999) == 999
    assert ad.system.settings.clamp_textract_max_concurrent(2000) == 1024
    assert ad.system.settings.clamp_textract_max_concurrent(-5) == 0


def test_clamp_llm_max_concurrent():
    assert ad.system.settings.clamp_llm_max_concurrent(8) == 8
    assert ad.system.settings.clamp_llm_max_concurrent(0) == 0


def test_default_worker_counts():
    assert ad.system.worker_counts.default_worker_counts() == ad.system.worker_counts.WorkerCounts()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, True),
        ("1", True),
        ("true", True),
        ("0", False),
        ("false", False),
    ],
)
def test_docrouter_queue_workers_enabled_in_process(monkeypatch, value, expected):
    monkeypatch.delenv("DOCROUTER_WORKERS_ENABLED", raising=False)
    if value is not None:
        monkeypatch.setenv("DOCROUTER_WORKERS_ENABLED", value)
    assert ad.system.workers.docrouter_queue_workers_enabled_in_process() is expected


@pytest.mark.asyncio
async def test_get_textract_max_concurrent_refreshes_every_25_requests(monkeypatch, test_db):
    ad.system.settings.reset_system_settings_cache()

    await test_db.system_settings.update_one(
        {"_id": ad.system.settings.SYSTEM_SETTINGS_ID},
        {"$set": {"textract_max_concurrent": 10}},
        upsert=True,
    )

    load_calls = 0
    original_load = ad.system.settings.load_textract_max_concurrent_from_db

    async def counting_load():
        nonlocal load_calls
        load_calls += 1
        return await original_load()

    monkeypatch.setattr(
        ad.system.settings,
        "load_textract_max_concurrent_from_db",
        counting_load,
    )

    value = await ad.system.settings.get_textract_max_concurrent()
    assert value == 10
    assert load_calls == 1

    for _ in range(25):
        value = await ad.system.settings.get_textract_max_concurrent()
        assert value == 10
    assert load_calls == 1

    value = await ad.system.settings.get_textract_max_concurrent()
    assert value == 10
    assert load_calls == 2


@pytest.mark.asyncio
async def test_seed_system_settings_if_missing(test_db):
    assert await ad.system.settings.seed_system_settings_if_missing() is True
    doc = await test_db.system_settings.find_one({"_id": ad.system.settings.SYSTEM_SETTINGS_ID})
    assert doc is not None
    assert doc["textract_max_concurrent"] == ad.system.settings.default_textract_max_concurrent()
    assert doc.get("llm_max_concurrent_by_model", {}) == {}
    assert doc["n_ocr_workers"] == 4

    assert await ad.system.settings.seed_system_settings_if_missing() is False


@pytest.mark.asyncio
async def test_update_system_settings_invalidates_cache(test_db):
    await test_db.system_settings.update_one(
        {"_id": ad.system.settings.SYSTEM_SETTINGS_ID},
        {"$set": {"textract_max_concurrent": 5, "n_ocr_workers": 1}},
        upsert=True,
    )
    ad.system.settings.reset_system_settings_cache()
    assert await ad.system.settings.get_textract_max_concurrent() == 5
    assert (await ad.system.settings.get_worker_counts()).n_ocr_workers == 1

    await ad.system.settings.update_system_settings(
        textract_max_concurrent=20,
        n_ocr_workers=3,
    )

    assert await ad.system.settings.get_textract_max_concurrent() == 20
    assert (await ad.system.settings.get_worker_counts()).n_ocr_workers == 3

    doc = await test_db.system_settings.find_one({"_id": ad.system.settings.SYSTEM_SETTINGS_ID})
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
    assert body.get("llm_max_concurrent_by_model", {}) == {}
    assert 0 <= body["textract_max_concurrent"] <= 1024
    assert 0 <= body["n_ocr_workers"] <= 256

    response = client.patch(
        "/v0/account/system_settings",
        headers=get_auth_headers(),
        json={
            "textract_max_concurrent": 16,
            "n_llm_workers": 5,
            "llm_max_concurrent_by_model": {"gpt-4o-mini": 8},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["textract_max_concurrent"] == 16
    assert body["n_llm_workers"] == 5
    assert body["llm_max_concurrent_by_model"] == {"gpt-4o-mini": 8}

    ad.system.settings.invalidate_system_settings_cache()
    counts = await ad.system.settings.get_worker_counts()
    assert counts.n_llm_workers == 5
    assert await ad.system.settings.get_llm_max_concurrent_for_model("gpt-4o-mini") == 8
