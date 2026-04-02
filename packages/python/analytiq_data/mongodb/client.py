"""MongoDB Motor client: shared pools per event loop (one logical pool per loop in production)."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

_lock = threading.Lock()
# One Motor client per running asyncio loop id. Production (uvicorn) uses a single loop → one pool.
# Tests may use pytest-asyncio's loop and Starlette TestClient's loop in the same test; closing a
# client when switching loops would invalidate AsyncIOMotorDatabase handles still held on the first loop.
_clients_by_loop_id: dict[int, AsyncIOMotorClient] = {}
# Rare: sync bootstrap with no running loop (avoid creating per-loop entry).
_shared_client_no_loop: AsyncIOMotorClient | None = None


def _parse_optional_positive_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        v = int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; ignoring", name, raw)
        return None
    if v < 0:
        logger.warning("Invalid %s=%r (negative); ignoring", name, raw)
        return None
    return v


def _motor_client_kwargs() -> dict:
    """Constructor kwargs aligned with former sync MongoClient (DocumentDB) + optional pool tuning."""
    kwargs: dict = {
        "w": "majority",
        "retryWrites": False,
        # Do not set readPreference to secondaryPreferred on the shared client:
        # PyMongo transactions require primary; KB and other code use transactions.
    }
    max_pool = _parse_optional_positive_int("MONGODB_MAX_POOL_SIZE")
    if max_pool is not None:
        kwargs["maxPoolSize"] = max_pool
    min_pool = _parse_optional_positive_int("MONGODB_MIN_POOL_SIZE")
    if min_pool is not None:
        kwargs["minPoolSize"] = min_pool
    max_idle = _parse_optional_positive_int("MONGODB_MAX_IDLE_TIME_MS")
    if max_idle is not None:
        kwargs["maxIdleTimeMS"] = max_idle
    return kwargs


def _get_shared_async_client() -> AsyncIOMotorClient:
    """Return the Motor client for the current event loop (lazy init, thread-safe)."""
    global _shared_client_no_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if current_loop is not None:
        key = id(current_loop)
        with _lock:
            client = _clients_by_loop_id.get(key)
            if client is None:
                mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
                opts = _motor_client_kwargs()
                opts["io_loop"] = current_loop
                client = AsyncIOMotorClient(mongo_uri, **opts)
                _clients_by_loop_id[key] = client
            return client

    with _lock:
        if _shared_client_no_loop is None:
            mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
            opts = _motor_client_kwargs()
            _shared_client_no_loop = AsyncIOMotorClient(mongo_uri, **opts)
        return _shared_client_no_loop


def get_mongodb_client_async(env: str = "dev") -> AsyncIOMotorClient:
    """Return the Motor client for the current event loop.

    The ``env`` parameter is accepted for API compatibility; the database name
    is selected via ``client[env]`` on :class:`analytiq_data.common.client.AnalytiqClient`.
    """
    return _get_shared_async_client()


async def close_shared_async_client() -> None:
    """Close all registered Motor clients and release their pools. Safe to call multiple times.

    Motor's :meth:`~motor.motor_asyncio.AsyncIOMotorClient.close` delegates to
    PyMongo's synchronous ``MongoClient.close`` (not a coroutine).
    """
    global _shared_client_no_loop
    with _lock:
        clients = list(_clients_by_loop_id.values())
        _clients_by_loop_id.clear()
        solo = _shared_client_no_loop
        _shared_client_no_loop = None
    for c in clients:
        c.close()
    if solo is not None:
        solo.close()


def reset_shared_async_client_for_tests() -> None:
    """Close all Motor clients when no asyncio loop is running.

    Use only in fixtures that change ``MONGODB_URI`` to a different server in the
    same session. Tests that only vary ``ENV`` / database name do not need this.

    If an event loop is already running (e.g. pytest-asyncio), call
    ``await close_shared_async_client()`` instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(close_shared_async_client())
    else:
        raise RuntimeError(
            "reset_shared_async_client_for_tests() cannot run under an active event loop; "
            "await close_shared_async_client() from async test code instead."
        )
