"""
Ensure MongoDB Search indexes exist on KB vector collections (vector + lexical).

Used by schema migrations after backup/restore (mongod data without mongot catalog).
Skips cleanly when the cluster does not support ``createSearchIndexes`` / ``listSearchIndexes``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional, Set

from motor.motor_asyncio import AsyncIOMotorDatabase

from analytiq_data.kb_search_indexes import (
    KB_LEXICAL_INDEX_NAME,
    KB_VECTOR_INDEX_NAME,
    kb_lexical_search_index_definition,
    kb_vector_search_index_definition,
)

logger = logging.getLogger(__name__)

EnsureKbSearchIndexOutcome = Literal[
    "ok",
    "created",
    "skipped_no_collection",
    "skipped_unsupported",
]

REQUIRED_KB_SEARCH_INDEX_NAMES = (KB_VECTOR_INDEX_NAME, KB_LEXICAL_INDEX_NAME)

# Errors when mongod has no search coordinator / mongot (plain Community without search).
_SEARCH_UNSUPPORTED_HINTS = (
    "command not found",
    "no such command",
    "unrecognized command",
    "not authorized on",
    "search index management",
    "does not support",
    "not supported",
    "unknown command",
)


def is_kb_search_index_command_unsupported(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(hint in msg for hint in _SEARCH_UNSUPPORTED_HINTS)


def _parse_list_search_indexes_result(result: Dict[str, Any]) -> Set[str]:
    batch = result.get("cursor", {}).get("firstBatch")
    if batch is None:
        batch = result.get("indexes") or []
    names: Set[str] = set()
    for ix in batch:
        name = ix.get("name")
        if name:
            names.add(name)
    return names


async def list_kb_search_index_names(
    db: AsyncIOMotorDatabase,
    collection_name: str,
) -> Optional[Set[str]]:
    """
    Return search index names on ``collection_name``, or ``None`` if search commands are unavailable.
    """
    try:
        result = await db.command({"listSearchIndexes": collection_name})
        return _parse_list_search_indexes_result(result)
    except Exception as e:
        if is_kb_search_index_command_unsupported(e):
            return None
        raise


async def ensure_kb_search_indexes_on_collection(
    db: AsyncIOMotorDatabase,
    collection_name: str,
    embedding_dimensions: int,
) -> EnsureKbSearchIndexOutcome:
    """
    Create missing ``kb_vector_index`` / ``kb_lexical_index`` on an existing vector collection.

    Idempotent: existing indexes are left unchanged (mapping updates are separate migrations).
    """
    collections = await db.list_collection_names()
    if collection_name not in collections:
        return "skipped_no_collection"

    existing = await list_kb_search_index_names(db, collection_name)
    if existing is None:
        return "skipped_unsupported"

    missing = [name for name in REQUIRED_KB_SEARCH_INDEX_NAMES if name not in existing]
    if not missing:
        return "ok"

    indexes_to_create: List[Dict[str, Any]] = []
    if KB_VECTOR_INDEX_NAME in missing:
        indexes_to_create.append(kb_vector_search_index_definition(embedding_dimensions))
    if KB_LEXICAL_INDEX_NAME in missing:
        indexes_to_create.append(kb_lexical_search_index_definition())

    try:
        await db.command({
            "createSearchIndexes": collection_name,
            "indexes": indexes_to_create,
        })
        logger.info(
            f"Created KB search index(es) {missing} on {collection_name}"
        )
        return "created"
    except Exception as e:
        err = str(e).lower()
        if (
            "already exists" in err
            or "duplicate" in err
            or "index already exists" in err
        ):
            return "ok"
        if is_kb_search_index_command_unsupported(e):
            return "skipped_unsupported"
        raise


async def ensure_all_kb_search_indexes(db: AsyncIOMotorDatabase) -> Dict[str, int]:
    """
    Ensure search indexes for every knowledge base that has a ``kb_vectors_*`` collection.

    Returns counts keyed by outcome (including ``skipped_unsupported`` as 1 when search is unavailable).
    """
    summary: Dict[str, int] = {
        "ok": 0,
        "created": 0,
        "skipped_no_collection": 0,
        "skipped_unsupported": 0,
        "collections_checked": 0,
    }

    kbs = await db.knowledge_bases.find(
        {},
        projection={"_id": 1, "embedding_dimensions": 1},
    ).to_list(length=None)
    collection_names = set(await db.list_collection_names())

    for kb in kbs:
        kb_id = str(kb["_id"])
        coll_name = f"kb_vectors_{kb_id}"
        if coll_name not in collection_names:
            continue

        summary["collections_checked"] += 1
        dims = int(kb.get("embedding_dimensions") or 1536)
        outcome = await ensure_kb_search_indexes_on_collection(db, coll_name, dims)
        summary[outcome] += 1

        if outcome == "skipped_unsupported":
            logger.info(
                "MongoDB Search index commands unavailable; skipping KB search index ensure "
                f"(checked {summary['collections_checked']} collection(s) before skip)"
            )
            break

    return summary
