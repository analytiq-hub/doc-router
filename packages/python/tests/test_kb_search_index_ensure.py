"""Tests for KB search index ensure (post-restore / non-Atlas skip)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from analytiq_data.kb_search_index_ensure import (
    ensure_all_kb_search_indexes,
    ensure_kb_search_indexes_on_collection,
    is_kb_search_index_command_unsupported,
    list_kb_search_index_names,
)


def test_is_kb_search_index_command_unsupported():
    assert is_kb_search_index_command_unsupported(Exception("no such command: listSearchIndexes"))
    assert is_kb_search_index_command_unsupported(Exception("Search index management is not supported"))
    assert not is_kb_search_index_command_unsupported(Exception("duplicate key"))


@pytest.mark.asyncio
async def test_list_kb_search_index_names_returns_none_when_unsupported():
    db = MagicMock()
    db.command = AsyncMock(side_effect=Exception("no such command: listSearchIndexes"))
    names = await list_kb_search_index_names(db, "kb_vectors_abc")
    assert names is None


@pytest.mark.asyncio
async def test_ensure_collection_creates_missing_indexes():
    db = MagicMock()
    db.list_collection_names = AsyncMock(return_value=["kb_vectors_abc"])
    db.command = AsyncMock(
        side_effect=[
            {"cursor": {"firstBatch": []}},
            {"ok": 1},
        ]
    )

    outcome = await ensure_kb_search_indexes_on_collection(db, "kb_vectors_abc", 1536)
    assert outcome == "created"
    create_call = db.command.call_args_list[1][0][0]
    assert create_call["createSearchIndexes"] == "kb_vectors_abc"
    created_names = {ix["name"] for ix in create_call["indexes"]}
    assert created_names == {"kb_vector_index", "kb_lexical_index"}


@pytest.mark.asyncio
async def test_ensure_collection_ok_when_indexes_present():
    db = MagicMock()
    db.list_collection_names = AsyncMock(return_value=["kb_vectors_abc"])
    db.command = AsyncMock(
        return_value={
            "cursor": {
                "firstBatch": [
                    {"name": "kb_vector_index"},
                    {"name": "kb_lexical_index"},
                ]
            }
        }
    )

    outcome = await ensure_kb_search_indexes_on_collection(db, "kb_vectors_abc", 1536)
    assert outcome == "ok"
    assert db.command.await_count == 1


@pytest.mark.asyncio
async def test_ensure_collection_skips_unsupported():
    db = MagicMock()
    db.list_collection_names = AsyncMock(return_value=["kb_vectors_abc"])
    db.command = AsyncMock(side_effect=Exception("unknown command createSearchIndexes"))

    outcome = await ensure_kb_search_indexes_on_collection(db, "kb_vectors_abc", 1536)
    assert outcome == "skipped_unsupported"


@pytest.mark.asyncio
async def test_ensure_all_stops_after_unsupported():
    db = MagicMock()
    kb_a = "aaaaaaaaaaaaaaaaaaaaaaaa"
    kb_b = "bbbbbbbbbbbbbbbbbbbbbbbb"
    db.list_collection_names = AsyncMock(
        return_value=[f"kb_vectors_{kb_a}", f"kb_vectors_{kb_b}"]
    )
    db.knowledge_bases.find = MagicMock(
        return_value=AsyncMock(
            to_list=AsyncMock(
                return_value=[
                    {"_id": kb_a, "embedding_dimensions": 1536},
                    {"_id": kb_b, "embedding_dimensions": 1536},
                ]
            )
        )
    )
    db.command = AsyncMock(side_effect=Exception("no such command: listSearchIndexes"))

    summary = await ensure_all_kb_search_indexes(db)
    assert summary["collections_checked"] == 1
    assert summary["skipped_unsupported"] == 1
