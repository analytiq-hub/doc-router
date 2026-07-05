import asyncio

import pytest

import analytiq_data as ad


def test_clamp_llm_max_concurrent():
    assert ad.system.settings.clamp_llm_max_concurrent(16) == 16
    assert ad.system.settings.clamp_llm_max_concurrent(0) == 0
    assert ad.system.settings.clamp_llm_max_concurrent(2000) == 1024
    assert ad.system.settings.clamp_llm_max_concurrent(-5) == 0


def test_normalize_llm_max_concurrent_by_model():
    assert ad.system.settings.normalize_llm_max_concurrent_by_model({}) == {}
    assert ad.system.settings.normalize_llm_max_concurrent_by_model(
        {"gpt-4o-mini": 8, "": 4, "bad": "x", "zero": 0}
    ) == {"gpt-4o-mini": 8}


@pytest.mark.asyncio
async def test_llm_concurrency_serializes_when_limit_one(monkeypatch):
    async def _limit_one(model: str) -> int:
        return 1 if model == "model-a" else 0

    monkeypatch.setattr(ad.system.settings, "get_llm_max_concurrent_for_model", _limit_one)
    ad.llm.reset_llm_concurrency_gates()

    active = 0
    max_active = 0
    lock = asyncio.Lock()
    first_holding = asyncio.Event()
    release = asyncio.Event()

    async def gated() -> None:
        nonlocal active, max_active
        async with ad.llm.llm_concurrency("model-a"):
            async with lock:
                active += 1
                max_active = max(max_active, active)
            first_holding.set()
            await release.wait()
            async with lock:
                active -= 1

    first = asyncio.create_task(gated())
    await first_holding.wait()
    second = asyncio.create_task(gated())
    await asyncio.sleep(0)
    async with lock:
        assert active == 1
        assert max_active == 1

    release.set()
    await asyncio.gather(first, second)
    assert max_active == 1


@pytest.mark.asyncio
async def test_llm_concurrency_independent_per_model(monkeypatch):
    async def _limits(model: str) -> int:
        return 1

    monkeypatch.setattr(ad.system.settings, "get_llm_max_concurrent_for_model", _limits)
    ad.llm.reset_llm_concurrency_gates()

    a_holding = asyncio.Event()
    release = asyncio.Event()
    b_started = asyncio.Event()

    async def hold_a():
        async with ad.llm.llm_concurrency("model-a"):
            a_holding.set()
            await release.wait()

    async def run_b():
        await a_holding.wait()
        async with ad.llm.llm_concurrency("model-b"):
            b_started.set()

    holder = asyncio.create_task(hold_a())
    await a_holding.wait()
    runner = asyncio.create_task(run_b())
    await asyncio.wait_for(b_started.wait(), timeout=1.0)

    release.set()
    await asyncio.gather(holder, runner)


@pytest.mark.asyncio
async def test_llm_concurrency_zero_limit_bypasses_gate(monkeypatch):
    async def _unlimited(_model: str) -> int:
        return 0

    monkeypatch.setattr(ad.system.settings, "get_llm_max_concurrent_for_model", _unlimited)
    ad.llm.reset_llm_concurrency_gates()

    entered = 0
    lock = asyncio.Lock()

    async def run():
        nonlocal entered
        async with ad.llm.llm_concurrency("model-a"):
            async with lock:
                entered += 1

    await asyncio.gather(run(), run())
    assert entered == 2


@pytest.mark.asyncio
async def test_get_llm_max_concurrent_for_model_refreshes_every_25_requests(monkeypatch, test_db):
    ad.system.settings.reset_system_settings_cache()

    await test_db.system_settings.update_one(
        {"_id": ad.system.settings.SYSTEM_SETTINGS_ID},
        {"$set": {"llm_max_concurrent_by_model": {"gpt-4o-mini": 4}}},
        upsert=True,
    )

    load_calls = 0
    original_load = ad.system.settings.load_llm_max_concurrent_map_from_db

    async def counting_load():
        nonlocal load_calls
        load_calls += 1
        return await original_load()

    monkeypatch.setattr(
        ad.system.settings,
        "load_llm_max_concurrent_map_from_db",
        counting_load,
    )

    value = await ad.system.settings.get_llm_max_concurrent_for_model("gpt-4o-mini")
    assert value == 4
    assert load_calls == 1

    for _ in range(25):
        value = await ad.system.settings.get_llm_max_concurrent_for_model("gpt-4o-mini")
        assert value == 4
    assert load_calls == 1

    value = await ad.system.settings.get_llm_max_concurrent_for_model("gpt-4o-mini")
    assert value == 4
    assert load_calls == 2

    assert await ad.system.settings.get_llm_max_concurrent_for_model("other-model") == 0
