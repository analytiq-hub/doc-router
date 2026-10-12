"""Unit tests for KB hybrid search Atlas Search filter clauses."""

from bson import ObjectId

from analytiq_data.kb.search import (
    _lexical_text_must_clause,
    build_atlas_search_filter_clauses,
    build_vector_search_filter,
)
from analytiq_data.kb_search_indexes import kb_lexical_search_index_definition


def test_lexical_index_maps_filter_fields_as_token():
    fields = kb_lexical_search_index_definition()["definition"]["mappings"]["fields"]
    assert fields["organization_id"] == {"type": "token"}
    tag_ids = fields["metadata_snapshot"]["fields"]["tag_ids"]
    assert tag_ids == {"type": "token"}


def test_atlas_search_filter_uses_string_tokens():
    org_id = "507f1f77bcf86cd799439011"
    tag_id = "67b560fa0000000000000001"
    filter_dict, _ = build_vector_search_filter(
        org_id,
        metadata_filter={"tag_ids": [tag_id]},
    )
    clauses = build_atlas_search_filter_clauses(filter_dict)
    assert {"equals": {"path": "organization_id", "value": org_id}} in clauses
    tag_clause = next(c for c in clauses if "in" in c)
    assert tag_clause == {
        "in": {"path": "metadata_snapshot.tag_ids", "value": [tag_id]},
    }


def test_lexical_text_searches_chunk_and_heading_path():
    clause = _lexical_text_must_clause("balance sheet")
    assert clause == {
        "text": {"query": "balance sheet", "path": ["chunk_text", "heading_path"]},
    }


def test_atlas_search_tag_filter_coerces_object_ids_to_strings():
    oid = ObjectId("67b560fa0000000000000001")
    filter_dict, _ = build_vector_search_filter(
        "org-1",
        metadata_filter={"tag_ids": [oid]},
    )
    clauses = build_atlas_search_filter_clauses(filter_dict)
    tag_clause = next(c for c in clauses if "in" in c)
    assert tag_clause["in"]["value"] == [str(oid)]
