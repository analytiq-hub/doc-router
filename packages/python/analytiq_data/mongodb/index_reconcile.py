"""Deploy-time MongoDB index reconcile (under migration lock only)."""

from __future__ import annotations

import json
import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from .index_registry import (
    DEPRECATED_INDEXES,
    all_reconcile_index_specs,
    IndexSpec,
)

logger = logging.getLogger(__name__)


def _normalize_index_keys(key: Any) -> list[tuple[str, int]]:
    if isinstance(key, dict):
        return [(str(field), int(direction)) for field, direction in key.items()]
    return [(str(field), int(direction)) for field, direction in key]


def _normalize_filter_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalize_filter_value(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        if value and all(isinstance(item, str) for item in value):
            return sorted(value)
        return [_normalize_filter_value(item) for item in value]
    return value


def _normalize_partial_filter(partial_filter: dict[str, Any] | None) -> str | None:
    if partial_filter is None:
        return None
    return json.dumps(_normalize_filter_value(partial_filter), sort_keys=True)


def _live_partial_filter(live_index: dict[str, Any]) -> str | None:
    expr = live_index.get("partialFilterExpression")
    if not expr:
        return None
    return _normalize_partial_filter(expr)


def _spec_partial_filter(spec: IndexSpec) -> str | None:
    return _normalize_partial_filter(spec.partial_filter)


def index_definition_matches(live_index: dict[str, Any], spec: IndexSpec) -> bool:
    """Return True when index options match ``spec`` (ignoring index name)."""
    if _normalize_index_keys(live_index.get("key")) != spec.keys:
        return False
    if bool(live_index.get("unique", False)) != spec.unique:
        return False
    if bool(live_index.get("sparse", False)) != spec.sparse:
        return False
    if _live_partial_filter(live_index) != _spec_partial_filter(spec):
        return False

    live_ttl = live_index.get("expireAfterSeconds")
    if spec.expire_after_seconds is None:
        if live_ttl is not None:
            return False
    elif live_ttl != spec.expire_after_seconds:
        return False

    return True


def index_spec_matches(live_index: dict[str, Any], spec: IndexSpec) -> bool:
    """Return True when a live ``list_indexes`` document matches ``spec``."""
    if live_index.get("name") != spec.name:
        return False
    return index_definition_matches(live_index, spec)


def _create_index_kwargs(spec: IndexSpec) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"name": spec.name}
    if spec.unique:
        kwargs["unique"] = True
    if spec.sparse:
        kwargs["sparse"] = True
    if spec.partial_filter is not None:
        kwargs["partialFilterExpression"] = spec.partial_filter
    if spec.expire_after_seconds is not None:
        kwargs["expireAfterSeconds"] = spec.expire_after_seconds
    if spec.background:
        kwargs["background"] = True
    return kwargs


async def _list_indexes_by_name(db: AsyncIOMotorDatabase, collection: str) -> dict[str, dict[str, Any]]:
    indexes = await db[collection].list_indexes().to_list(length=None)
    return {idx["name"]: idx for idx in indexes}


def _find_legacy_index_with_same_keys(
    live_by_name: dict[str, dict[str, Any]],
    spec: IndexSpec,
) -> dict[str, Any] | None:
    """Find a non-_id index on the same key pattern under a different name."""
    for idx in live_by_name.values():
        name = idx.get("name")
        if name in ("_id_", spec.name):
            continue
        if _normalize_index_keys(idx.get("key")) == spec.keys:
            return idx
    return None


async def _reconcile_one_index(
    db: AsyncIOMotorDatabase,
    spec: IndexSpec,
    summary: dict[str, int],
) -> None:
    if spec.skip_if_collection_missing:
        if spec.collection not in await db.list_collection_names():
            return

    live_by_name = await _list_indexes_by_name(db, spec.collection)
    live = live_by_name.get(spec.name)
    collection = db[spec.collection]
    create_kwargs = _create_index_kwargs(spec)

    if live is None:
        legacy = _find_legacy_index_with_same_keys(live_by_name, spec)
        if legacy is not None:
            legacy_name = legacy["name"]
            if index_definition_matches(legacy, spec):
                logger.info(
                    f"Renaming legacy index {legacy_name} to {spec.name} on {spec.collection}"
                )
            else:
                logger.warning(
                    f"Replacing legacy index {legacy_name} with {spec.name} "
                    f"on {spec.collection} (definition differs)"
                )
            await collection.drop_index(legacy_name)
            await collection.create_index(spec.keys, **create_kwargs)
            summary["updated"] += 1
            logger.info(f"Ensured index {spec.name} on {spec.collection}")
            return

        await collection.create_index(spec.keys, **create_kwargs)
        summary["created"] += 1
        logger.info(f"Created index {spec.name} on {spec.collection}")
        return

    if index_spec_matches(live, spec):
        summary["unchanged"] += 1
        return

    logger.warning(
        f"Index {spec.name} on {spec.collection} does not match registry spec; recreating"
    )
    await collection.drop_index(spec.name)
    await collection.create_index(spec.keys, **create_kwargs)
    summary["updated"] += 1
    logger.info(f"Recreated index {spec.name} on {spec.collection}")


async def ensure_runtime_indexes(db: AsyncIOMotorDatabase) -> None:
    """
    Create-only index safety net for FastAPI lifespan and local dev without migrate.

    Uses the same registry as ``reconcile_indexes`` but never drops or recreates indexes.
    Spec drift and legacy renames are handled by reconcile under the migration lock.
    """
    collection_names = set(await db.list_collection_names())
    specs = all_reconcile_index_specs(collection_names)

    indexes_by_collection: dict[str, dict[str, dict[str, Any]]] = {}
    for spec in specs:
        if spec.skip_if_collection_missing and spec.collection not in collection_names:
            continue

        if spec.collection not in indexes_by_collection:
            indexes_by_collection[spec.collection] = await _list_indexes_by_name(db, spec.collection)

        live_by_name = indexes_by_collection[spec.collection]
        if spec.name in live_by_name:
            continue
        if _find_legacy_index_with_same_keys(live_by_name, spec) is not None:
            continue

        await db[spec.collection].create_index(spec.keys, **_create_index_kwargs(spec))
        logger.debug(f"Ensured runtime index {spec.name} on {spec.collection}")


async def reconcile_indexes(db: AsyncIOMotorDatabase) -> dict[str, int]:
    """
    Sync curated indexes under the migration lock.

    Creates missing indexes, drop+recreates on spec mismatch, renames legacy same-key
    indexes, and drops deprecated names. Does not touch unlisted indexes.
    """
    summary = {"created": 0, "updated": 0, "dropped": 0, "unchanged": 0}
    collection_names = set(await db.list_collection_names())

    for spec in all_reconcile_index_specs(collection_names):
        await _reconcile_one_index(db, spec, summary)

    for spec in DEPRECATED_INDEXES:
        if spec.collection not in collection_names:
            continue
        live_by_name = await _list_indexes_by_name(db, spec.collection)
        if spec.name not in live_by_name:
            continue
        try:
            await db[spec.collection].drop_index(spec.name)
            summary["dropped"] += 1
            logger.info(f"Dropped deprecated index {spec.name} on {spec.collection}")
        except Exception as exc:
            logger.warning(
                f"Failed to drop deprecated index {spec.name} on {spec.collection}: {exc}"
            )

    logger.info(
        "Index reconcile complete: "
        f"created={summary['created']} updated={summary['updated']} "
        f"dropped={summary['dropped']} unchanged={summary['unchanged']}"
    )
    return summary
