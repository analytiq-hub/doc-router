"""Unit tests for KB search retrieval paths (hybrid fallback, min_vector_score)."""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.kb.search import _vector_only_pipeline, search_knowledge_base

from .conftest_utils import TEST_ORG_ID
from .kb_test_helpers import MOCK_EMBEDDING_DIMENSIONS, insert_minimal_kb, insert_org_tag

FAKE_EMBEDDING = [0.001] * MOCK_EMBEDDING_DIMENSIONS

SAMPLE_HIT = {
    "chunk_text": "Balance sheet totals",
    "document_id": "doc-1",
    "chunk_index": 0,
    "score": 0.42,
    "metadata_snapshot": {"document_name": "report.pdf"},
}


def _top_level_stage_keys(pipeline: List[Dict[str, Any]]) -> List[str]:
    return [next(iter(stage)) for stage in pipeline]


def _min_vector_score_in_pipeline(pipeline: List[Dict[str, Any]]) -> Optional[float]:
    for stage in pipeline:
        match = stage.get("$match")
        if isinstance(match, dict) and "score" in match:
            gte = match["score"].get("$gte")
            if gte is not None:
                return float(gte)
    return None


def test_vector_only_pipeline_includes_min_score_when_set():
    pipeline = _vector_only_pipeline(
        query_embedding=FAKE_EMBEDDING,
        search_filter={"organization_id": TEST_ORG_ID},
        post_filter={},
        branch_limit=25,
        num_candidates=500,
        skip=0,
        top_k=5,
        min_vector_score=0.75,
    )
    assert _min_vector_score_in_pipeline(pipeline) == 0.75
    assert _top_level_stage_keys(pipeline)[0] == "$vectorSearch"


def test_vector_only_pipeline_omits_min_score_when_none():
    pipeline = _vector_only_pipeline(
        query_embedding=FAKE_EMBEDDING,
        search_filter={"organization_id": TEST_ORG_ID},
        post_filter={},
        branch_limit=25,
        num_candidates=500,
        skip=0,
        top_k=5,
        min_vector_score=None,
    )
    assert _min_vector_score_in_pipeline(pipeline) is None


@pytest.mark.asyncio
@patch("analytiq_data.kb.search._execute_vector_search_with_retry", new_callable=AsyncMock)
@patch("analytiq_data.kb.search.get_embedding_from_cache", new_callable=AsyncMock)
async def test_empty_query_applies_min_vector_score_on_vector_only(
    mock_cache,
    mock_exec,
    test_db,
    mock_auth,
    setup_test_models,
):
    mock_cache.return_value = FAKE_EMBEDDING
    mock_exec.return_value = []

    kb_id = await insert_minimal_kb(test_db, [], name="Browse KB")
    await test_db.knowledge_bases.update_one(
        {"_id": ObjectId(kb_id)},
        {"$set": {"min_vector_score": 0.8}},
    )

    analytiq_client = ad.common.get_analytiq_client()
    await search_knowledge_base(
        analytiq_client,
        kb_id,
        query="   ",
        organization_id=TEST_ORG_ID,
        top_k=5,
        coalesce_neighbors=0,
    )

    assert mock_exec.call_count == 1
    pipeline = mock_exec.call_args[0][1]
    assert _top_level_stage_keys(pipeline)[0] == "$vectorSearch"
    assert "$rankFusion" not in str(pipeline)
    assert _min_vector_score_in_pipeline(pipeline) == 0.8


@pytest.mark.asyncio
@patch("analytiq_data.kb.search._execute_vector_search_with_retry", new_callable=AsyncMock)
@patch("analytiq_data.kb.search.get_embedding_from_cache", new_callable=AsyncMock)
async def test_non_empty_query_skips_min_vector_score_on_rankfusion_fallback(
    mock_cache,
    mock_exec,
    test_db,
    mock_auth,
    setup_test_models,
):
    mock_cache.return_value = FAKE_EMBEDDING
    mock_exec.side_effect = [
        Exception("Unrecognized aggregation stage $rankFusion"),
        [SAMPLE_HIT],
    ]

    kb_id = await insert_minimal_kb(test_db, [], name="Fusion fallback KB")
    await test_db.knowledge_bases.update_one(
        {"_id": ObjectId(kb_id)},
        {"$set": {"min_vector_score": 0.95}},
    )

    analytiq_client = ad.common.get_analytiq_client()
    out = await search_knowledge_base(
        analytiq_client,
        kb_id,
        query="balance sheet",
        organization_id=TEST_ORG_ID,
        top_k=5,
        coalesce_neighbors=0,
    )

    assert mock_exec.call_count == 2
    fallback_pipeline = mock_exec.call_args_list[1][0][1]
    assert _top_level_stage_keys(fallback_pipeline)[0] == "$vectorSearch"
    assert _min_vector_score_in_pipeline(fallback_pipeline) is None
    assert len(out["results"]) == 1
    assert out["results"][0]["content"] == SAMPLE_HIT["chunk_text"]


@pytest.mark.asyncio
@patch("analytiq_data.kb.search._execute_vector_search_with_retry", new_callable=AsyncMock)
@patch("analytiq_data.kb.search.get_embedding_from_cache", new_callable=AsyncMock)
async def test_hybrid_empty_results_retries_vector_only_without_min_score(
    mock_cache,
    mock_exec,
    test_db,
    mock_auth,
    setup_test_models,
):
    mock_cache.return_value = FAKE_EMBEDDING
    mock_exec.side_effect = [[], [SAMPLE_HIT]]

    kb_id = await insert_minimal_kb(test_db, [], name="Hybrid empty KB")
    await test_db.knowledge_bases.update_one(
        {"_id": ObjectId(kb_id)},
        {"$set": {"min_vector_score": 0.99}},
    )

    analytiq_client = ad.common.get_analytiq_client()
    out = await search_knowledge_base(
        analytiq_client,
        kb_id,
        query="balance sheet",
        organization_id=TEST_ORG_ID,
        top_k=5,
        coalesce_neighbors=0,
    )

    assert mock_exec.call_count == 2
    hybrid_pipeline = mock_exec.call_args_list[0][0][1]
    retry_pipeline = mock_exec.call_args_list[1][0][1]
    assert _top_level_stage_keys(hybrid_pipeline)[0] == "$rankFusion"
    assert _top_level_stage_keys(retry_pipeline)[0] == "$vectorSearch"
    assert _min_vector_score_in_pipeline(retry_pipeline) is None
    assert len(out["results"]) == 1


@pytest.mark.asyncio
@patch("analytiq_data.kb.search._execute_vector_search_with_retry", new_callable=AsyncMock)
@patch("analytiq_data.kb.search.get_embedding_from_cache", new_callable=AsyncMock)
async def test_hybrid_with_results_does_not_retry_vector_only(
    mock_cache,
    mock_exec,
    test_db,
    mock_auth,
    setup_test_models,
):
    mock_cache.return_value = FAKE_EMBEDDING
    mock_exec.return_value = [SAMPLE_HIT]

    tag_id = await insert_org_tag(test_db, "Search tag")
    kb_id = await insert_minimal_kb(test_db, [tag_id], name="Hybrid hit KB")

    analytiq_client = ad.common.get_analytiq_client()
    await search_knowledge_base(
        analytiq_client,
        kb_id,
        query="balance sheet",
        organization_id=TEST_ORG_ID,
        top_k=5,
        coalesce_neighbors=0,
    )

    assert mock_exec.call_count == 1
    pipeline = mock_exec.call_args[0][1]
    assert _top_level_stage_keys(pipeline)[0] == "$rankFusion"
    lexical_branch = pipeline[0]["$rankFusion"]["input"]["pipelines"]["lexical"]
    search_stage = lexical_branch[0]["$search"]
    assert search_stage["index"] == "kb_lexical_index"
    must_clause = search_stage["compound"]["must"][0]
    assert must_clause["text"]["path"] == ["chunk_text", "heading_path"]
    filter_clauses = search_stage["compound"]["filter"]
    assert {"equals": {"path": "organization_id", "value": TEST_ORG_ID}} in filter_clauses
