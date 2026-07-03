"""Curated MongoDB index definitions for deploy-time reconcile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Shared with docrouter event-trigger dedupe queries and reconcile.
ACTIVE_FLOW_DOCUMENT_STATUSES = ("queued", "running")
FLOW_EXECUTIONS_ACTIVE_FLOW_DOCUMENT_INDEX = "flow_executions_active_flow_document_unique"
ACTIVE_FLOW_DOCUMENT_DEDUPE_PARTIAL_FILTER: dict[str, Any] = {
    "status": {"$in": list(ACTIVE_FLOW_DOCUMENT_STATUSES)},
    "trigger.document_id": {"$exists": True, "$type": "string", "$gt": ""},
}

# Worker queue collections that share the same index shape (see WORKER_QUEUE_INDEX_TEMPLATES).
WORKER_QUEUE_COLLECTIONS: tuple[str, ...] = (
    "queues.ocr",
    "queues.llm",
    "queues.webhook",
    "queues.kb_index",
    "queues.flow_run",
)


@dataclass(frozen=True)
class IndexSpec:
    collection: str
    name: str
    keys: list[tuple[str, int]]
    unique: bool = False
    sparse: bool = False
    partial_filter: dict[str, Any] | None = None
    expire_after_seconds: int | None = None
    background: bool = True
    # GridFS buckets: skip until first upload created the namespace.
    skip_if_collection_missing: bool = False


def _spec(
    collection: str,
    name: str,
    keys: list[tuple[str, int]] | list[tuple[str, int]],
    *,
    unique: bool = False,
    sparse: bool = False,
    partial_filter: dict[str, Any] | None = None,
    expire_after_seconds: int | None = None,
    skip_if_collection_missing: bool = False,
) -> IndexSpec:
    return IndexSpec(
        collection=collection,
        name=name,
        keys=keys,
        unique=unique,
        sparse=sparse,
        partial_filter=partial_filter,
        expire_after_seconds=expire_after_seconds,
        skip_if_collection_missing=skip_if_collection_missing,
    )


# --- Phase 1: startup / flow / payments paths ---

_PHASE1_INDEXES: tuple[IndexSpec, ...] = (
    _spec(
        "embedding_cache",
        "chunk_hash_embedding_model_unique",
        [("chunk_hash", 1), ("embedding_model", 1)],
        unique=True,
    ),
    _spec(
        "credentials",
        "credentials_org_kind_key",
        [("organization_id", 1), ("kind_key", 1)],
    ),
    _spec(
        "flow_oauth_states",
        "flow_oauth_states_ttl",
        [("expires_at", 1)],
        expire_after_seconds=0,
    ),
    _spec(
        "payments_usage_records",
        "org_timestamp_idx",
        [("org_id", 1), ("timestamp", 1)],
    ),
    _spec(
        "flow_static_data",
        "flow_static_data_flow_node_unique",
        [("flow_id", 1), ("node_id", 1)],
        unique=True,
    ),
    _spec(
        "flow_trigger_leases",
        "flow_trigger_leases_expires_at_ttl",
        [("expires_at", 1)],
        expire_after_seconds=0,
    ),
    _spec(
        "flow_trigger_registrations",
        "flow_trigger_registrations_flow_node_rule_unique",
        [("flow_id", 1), ("node_id", 1), ("rule_index", 1)],
        unique=True,
    ),
    _spec(
        "flow_trigger_registrations",
        "flow_trigger_registrations_flow_id",
        [("flow_id", 1)],
    ),
    _spec(
        "flow_executions",
        "flow_executions_trigger_dedupe_key_unique",
        [("trigger.dedupe_key", 1)],
        unique=True,
        sparse=True,
    ),
    _spec(
        "flow_executions",
        FLOW_EXECUTIONS_ACTIVE_FLOW_DOCUMENT_INDEX,
        [("flow_id", 1), ("trigger.document_id", 1)],
        unique=True,
        partial_filter=ACTIVE_FLOW_DOCUMENT_DEDUPE_PARTIAL_FILTER,
    ),
    _spec(
        "flow_triggers",
        "flow_triggers_flow_node_unique",
        [("flow_id", 1), ("trigger_node_id", 1)],
        unique=True,
    ),
    _spec(
        "flow_triggers",
        "flow_triggers_org_trigger_type",
        [("org_id", 1), ("trigger_type", 1)],
    ),
    _spec(
        "flow_results",
        "flow_results_doc_flow_unique",
        [("document_id", 1), ("flow_id", 1)],
        unique=True,
    ),
    _spec(
        "flow_results",
        "flow_results_org_document",
        [("org_id", 1), ("document_id", 1)],
    ),
    _spec(
        "flow_results",
        "flow_results_org_flow",
        [("org_id", 1), ("flow_id", 1)],
    ),
)

# --- Phase 2: indexes previously created only in versioned migrations ---

_PHASE2_INDEXES: tuple[IndexSpec, ...] = (
    # access_tokens: HMAC fingerprint lookup (AddAccessTokenFingerprint)
    _spec(
        "access_tokens",
        "access_tokens_fingerprint_unique",
        [("fingerprint", 1)],
        unique=True,
    ),
    # webhook_deliveries (AddWebhookDeliveriesIndexes, AddWebhookDeliveriesWebhookIdIndex)
    _spec(
        "webhook_deliveries",
        "webhook_deliveries_org_created_at",
        [("organization_id", 1), ("created_at", -1)],
    ),
    _spec(
        "webhook_deliveries",
        "webhook_deliveries_status_next_attempt_at",
        [("status", 1), ("next_attempt_at", 1)],
    ),
    _spec(
        "webhook_deliveries",
        "webhook_deliveries_org_webhook_created_at",
        [("organization_id", 1), ("webhook_id", 1), ("created_at", -1)],
    ),
    # webhook_endpoints (AddWebhookEndpointsIndexes)
    _spec(
        "webhook_endpoints",
        "webhook_endpoints_org_created_at",
        [("organization_id", 1), ("created_at", 1)],
    ),
    # document_index (AddQueueAndCollectionIndexes)
    _spec(
        "document_index",
        "kb_id_document_id_unique_idx",
        [("kb_id", 1), ("document_id", 1)],
        unique=True,
    ),
    _spec(
        "document_index",
        "document_id_idx",
        [("document_id", 1)],
    ),
    # docs: paginated org listing
    _spec(
        "docs",
        "org_upload_date_idx",
        [("organization_id", 1), ("upload_date", -1)],
    ),
    # llm_runs: result lookups by prompt id / revision
    _spec(
        "llm_runs",
        "doc_prompt_version_idx",
        [("document_id", 1), ("prompt_id", 1), ("prompt_version", -1)],
    ),
    _spec(
        "llm_runs",
        "doc_prompt_revid_idx",
        [("document_id", 1), ("prompt_revid", 1)],
    ),
    # knowledge_bases: reconciliation polling
    _spec(
        "knowledge_bases",
        "reconcile_status_idx",
        [("reconcile_enabled", 1), ("status", 1)],
    ),
    # prompt_revisions: latest revision + list_prompts tag filter
    _spec(
        "prompt_revisions",
        "prompt_id_latest_idx",
        [("prompt_id", 1), ("_id", -1)],
    ),
    _spec(
        "prompt_revisions",
        "prompt_id_tag_ids_idx",
        [("prompt_id", 1), ("tag_ids", 1)],
    ),
    # schema_revisions: latest revision per schema
    _spec(
        "schema_revisions",
        "schema_id_latest_idx",
        [("schema_id", 1), ("_id", -1)],
    ),
    # prompts: list_prompts org filter
    _spec(
        "prompts",
        "organization_id_idx",
        [("organization_id", 1)],
    ),
    # credentials: unique label per org + list sort (AddCredentialsOrgNameUniqueIndex)
    _spec(
        "credentials",
        "credentials_org_name_unique",
        [("organization_id", 1), ("name", 1)],
        unique=True,
    ),
    _spec(
        "credentials",
        "credentials_org_updated_at",
        [("organization_id", 1), ("updated_at", -1)],
    ),
    # flow_executions / flows: org-scoped list queries (AddFlowExecutionsFlowsCredentialsListIndexes)
    _spec(
        "flow_executions",
        "flow_executions_org_started_at",
        [("organization_id", 1), ("started_at", -1)],
    ),
    _spec(
        "flow_executions",
        "flow_executions_org_flow_started_at",
        [("organization_id", 1), ("flow_id", 1), ("started_at", -1)],
    ),
    _spec(
        "flows",
        "flows_org_updated_at",
        [("organization_id", 1), ("updated_at", -1)],
    ),
    # chat_threads: document/KB thread listing (RenameAgentThreadsToChatThreads)
    _spec(
        "chat_threads",
        "chat_threads_doc_list_idx",
        [("organization_id", 1), ("document_id", 1), ("created_by", 1), ("updated_at", -1)],
    ),
    _spec(
        "chat_threads",
        "chat_threads_kb_list_idx",
        [("organization_id", 1), ("kb_id", 1), ("created_by", 1), ("updated_at", -1)],
    ),
    # GridFS (AddGridFSFilesBucketIndexes) — only when bucket namespaces exist
    _spec(
        "files.files",
        "filename_1_uploadDate_1",
        [("filename", 1), ("uploadDate", 1)],
        skip_if_collection_missing=True,
    ),
    _spec(
        "files.chunks",
        "files_id_1_n_1",
        [("files_id", 1), ("n", 1)],
        unique=True,
        skip_if_collection_missing=True,
    ),
    _spec(
        "ocr.files",
        "filename_1_uploadDate_1",
        [("filename", 1), ("uploadDate", 1)],
        skip_if_collection_missing=True,
    ),
    _spec(
        "ocr.chunks",
        "files_id_1_n_1",
        [("files_id", 1), ("n", 1)],
        unique=True,
        skip_if_collection_missing=True,
    ),
)

# Shared index definitions applied to each worker queue collection (and dynamic queues.kb_index_*).
WORKER_QUEUE_INDEX_TEMPLATES: tuple[IndexSpec, ...] = (
    # recv_pending_msg: claim oldest pending by created_at
    _spec(
        "_",
        "status_created_at_idx",
        [("status", 1), ("created_at", 1)],
    ),
    # recv_msg: reclaim stale processing messages
    _spec(
        "_",
        "status_processing_attempts_idx",
        [("status", 1), ("processing_started_at", 1), ("attempts", 1)],
    ),
)

EXPECTED_INDEXES: tuple[IndexSpec, ...] = _PHASE1_INDEXES + _PHASE2_INDEXES

# Legacy index superseded by access_tokens_fingerprint_unique (AddAccessTokenFingerprint).
DEPRECATED_INDEXES: tuple[IndexSpec, ...] = (
    _spec(
        "access_tokens",
        "token_1",
        [("token", 1)],
    ),
)


def expand_worker_queue_index_specs(collection_names: set[str] | frozenset[str]) -> tuple[IndexSpec, ...]:
    """Build per-collection queue index specs for static and dynamic kb_index queues."""
    queue_collections = list(WORKER_QUEUE_COLLECTIONS)
    for name in collection_names:
        if name.startswith("queues.kb_index_") and name not in queue_collections:
            queue_collections.append(name)

    specs: list[IndexSpec] = []
    for coll in queue_collections:
        if coll not in collection_names:
            continue
        for tmpl in WORKER_QUEUE_INDEX_TEMPLATES:
            specs.append(
                IndexSpec(
                    collection=coll,
                    name=tmpl.name,
                    keys=tmpl.keys,
                    unique=tmpl.unique,
                    sparse=tmpl.sparse,
                    partial_filter=tmpl.partial_filter,
                    expire_after_seconds=tmpl.expire_after_seconds,
                    background=tmpl.background,
                )
            )
    return tuple(specs)


def all_reconcile_index_specs(collection_names: set[str] | frozenset[str]) -> tuple[IndexSpec, ...]:
    """Full reconcile target list: fixed registry + worker queue collections present in ``db``."""
    fixed = tuple(
        spec
        for spec in EXPECTED_INDEXES
        if not (spec.skip_if_collection_missing and spec.collection not in collection_names)
    )
    return fixed + expand_worker_queue_index_specs(collection_names)
