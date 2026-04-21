"""MongoDB Motor client: shared pools per event loop (one logical pool per loop in production)."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import weakref
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

_lock = threading.Lock()
# One Motor client per running asyncio loop. WeakKeyDictionary keys on the loop object itself so
# entries are evicted automatically when a loop is garbage-collected, preventing stale lookups from
# loop-ID reuse (CPython can assign the same id() to a new loop after the old one is freed).
# Production (uvicorn) uses a single loop → one pool.
# Tests may use pytest-asyncio's loop and Starlette TestClient's loop in the same process.
_clients_by_loop: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, AsyncIOMotorClient] = (
    weakref.WeakKeyDictionary()
)
# Rare: sync bootstrap with no running loop (avoid creating per-loop entry).
_shared_client_no_loop: AsyncIOMotorClient | None = None


def _getenv_positive_int(name: str, default: int | None = None) -> int | None:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        v = int(raw)
    except ValueError:
        logger.warning(f"Invalid {name}={raw!r}; using default={default!r}")
        return default
    if v < 0:
        logger.warning(f"Invalid {name}={raw!r} (negative); using default={default!r}")
        return default
    return v


def _motor_client_kwargs() -> dict:
    """Constructor kwargs aligned with former sync MongoClient (DocumentDB) + optional pool tuning."""
    kwargs: dict = {
        "w": "majority",
        "retryWrites": False,
        # Do not set readPreference to secondaryPreferred on the shared client:
        # PyMongo transactions require primary; KB and other code use transactions.
    }

    # Pool tuning.
    #
    # We set non-trivial defaults to improve throughput for concurrent requests and worker queues.
    # Ops can override via env to respect Mongo cluster connection limits.
    kwargs["maxPoolSize"] = _getenv_positive_int("MONGODB_MAX_POOL_SIZE", 200)

    kwargs["minPoolSize"] = _getenv_positive_int("MONGODB_MIN_POOL_SIZE", 20)

    max_idle = _getenv_positive_int("MONGODB_MAX_IDLE_TIME_MS", None)
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
        with _lock:
            client = _clients_by_loop.get(current_loop)
            if client is None:
                mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
                # Motor 3.x auto-detects the running loop; no need to pass io_loop explicitly.
                client = AsyncIOMotorClient(mongo_uri, **_motor_client_kwargs())
                _clients_by_loop[current_loop] = client
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
        clients = list(_clients_by_loop.values())
        _clients_by_loop.clear()
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
