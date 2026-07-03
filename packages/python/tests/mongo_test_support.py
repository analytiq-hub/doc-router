"""Shared MongoDB helpers for the pytest suite."""

from __future__ import annotations

import os

from motor.motor_asyncio import AsyncIOMotorDatabase

import analytiq_data as ad

# Collections present when ensure_runtime_indexes last ran (per worker DB name).
_indexed_collections: dict[str, frozenset[str]] = {}


def worker_database_name() -> str:
    """Stable pytest database name per xdist worker or per session."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    if worker_id:
        return f"pytest_{worker_id}"
    return os.environ["ENV"]


def mongo_client_kwargs(mongo_uri: str) -> dict:
    """Small pools for tests — avoids connection storms under pytest-xdist."""
    kwargs: dict = {"maxPoolSize": 10, "minPoolSize": 0}
    if not mongo_uri.startswith("mongodb+srv://"):
        kwargs["directConnection"] = True
    return kwargs


def is_index_reconcile_test(node) -> bool:
    fspath = getattr(node, "fspath", None)
    return bool(fspath and "test_index_reconcile.py" in str(fspath))


async def ensure_runtime_indexes_for_new_collections(
    db: AsyncIOMotorDatabase, worker_key: str
) -> None:
    """Ensure indexes only when new collections appeared (e.g. queues.* mid-suite)."""
    current = frozenset(await db.list_collection_names())
    if current <= _indexed_collections.get(worker_key, frozenset()):
        return
    await ad.mongodb.ensure_runtime_indexes(db)
    _indexed_collections[worker_key] = current


def reset_index_tracking(worker_key: str) -> None:
    """Clear tracking after dropping all collections (index-reconcile tests)."""
    _indexed_collections.pop(worker_key, None)


async def clear_all_documents(db: AsyncIOMotorDatabase) -> None:
    """Remove all documents; indexes and collections are preserved."""
    for name in await db.list_collection_names():
        await db[name].delete_many({})


async def drop_all_collections(db: AsyncIOMotorDatabase) -> None:
    """Drop every collection (and its indexes). For index-reconcile tests only."""
    for name in await db.list_collection_names():
        await db.drop_collection(name)
