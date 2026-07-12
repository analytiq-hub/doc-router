"""Tests for app.startup admin bootstrap and pending schema migration gating."""

from unittest.mock import AsyncMock, patch

import pytest

from app import startup


@pytest.mark.asyncio
async def test_setup_admin_skips_when_admin_exists():
    client = AsyncMock()
    client.env = "test"
    db = AsyncMock()
    client.mongodb_async = {"test": db}
    db.users.find_one = AsyncMock(return_value={"email": "admin@example.com"})

    with patch.object(
        startup,
        "run_pending_schema_migrations_if_needed",
        new_callable=AsyncMock,
    ) as run_pending:
        await startup.setup_admin(client)

    run_pending.assert_not_called()


@pytest.mark.asyncio
async def test_setup_admin_runs_pending_migrations_when_admin_missing():
    client = AsyncMock()
    client.env = "test"
    db = AsyncMock()
    client.mongodb_async = {"test": db}
    db.users.find_one = AsyncMock(return_value=None)
    db.users.insert_one = AsyncMock(
        return_value=AsyncMock(inserted_id="507f1f77bcf86cd799439011")
    )
    db.organizations.insert_one = AsyncMock()

    with patch.dict(
        "os.environ",
        {"ADMIN_EMAIL": "admin@example.com", "ADMIN_PASSWORD": "secret"},
        clear=False,
    ):
        with patch.object(
            startup,
            "run_pending_schema_migrations_if_needed",
            new_callable=AsyncMock,
        ) as run_pending:
            await startup.setup_admin(client)

    run_pending.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_pending_schema_migrations_if_needed_skips_when_current(test_db):
    import analytiq_data as ad

    client = AsyncMock()
    client.env = test_db.name
    client.mongodb_async = {test_db.name: test_db}
    target_version = len(ad.migrations.MIGRATIONS)
    await test_db.migrations.insert_one(
        {"_id": "schema_version", "version": target_version}
    )

    with patch.object(
        startup.ad.migrations,
        "run_migrations",
        new_callable=AsyncMock,
    ) as run_migrations:
        await startup.run_pending_schema_migrations_if_needed(client)

    run_migrations.assert_not_called()


@pytest.mark.asyncio
async def test_run_pending_schema_migrations_if_needed_runs_when_behind(test_db):
    import analytiq_data as ad

    client = AsyncMock()
    client.env = test_db.name
    client.mongodb_async = {test_db.name: test_db}

    with patch.object(
        startup.ad.migrations,
        "run_migrations",
        new_callable=AsyncMock,
    ) as run_migrations:
        await startup.run_pending_schema_migrations_if_needed(client)

    run_migrations.assert_awaited_once_with(client)


@pytest.mark.asyncio
async def test_schema_migrations_pending(test_db):
    import analytiq_data as ad

    assert await ad.migrations.schema_migrations_pending(test_db) is True

    target_version = len(ad.migrations.MIGRATIONS)
    await test_db.migrations.insert_one(
        {"_id": "schema_version", "version": target_version}
    )
    assert await ad.migrations.schema_migrations_pending(test_db) is False
