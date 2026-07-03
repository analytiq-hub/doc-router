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


# Phase 1 registry: indexes ensured at startup today.
EXPECTED_INDEXES: tuple[IndexSpec, ...] = (
    IndexSpec(
        collection="embedding_cache",
        name="chunk_hash_embedding_model_unique",
        keys=[("chunk_hash", 1), ("embedding_model", 1)],
        unique=True,
    ),
    IndexSpec(
        collection="credentials",
        name="credentials_org_kind_key",
        keys=[("organization_id", 1), ("kind_key", 1)],
    ),
    IndexSpec(
        collection="flow_oauth_states",
        name="flow_oauth_states_ttl",
        keys=[("expires_at", 1)],
        expire_after_seconds=0,
    ),
    IndexSpec(
        collection="payments_usage_records",
        name="org_timestamp_idx",
        keys=[("org_id", 1), ("timestamp", 1)],
    ),
    IndexSpec(
        collection="flow_static_data",
        name="flow_static_data_flow_node_unique",
        keys=[("flow_id", 1), ("node_id", 1)],
        unique=True,
    ),
    IndexSpec(
        collection="flow_trigger_leases",
        name="flow_trigger_leases_expires_at_ttl",
        keys=[("expires_at", 1)],
        expire_after_seconds=0,
    ),
    IndexSpec(
        collection="flow_trigger_registrations",
        name="flow_trigger_registrations_flow_node_rule_unique",
        keys=[("flow_id", 1), ("node_id", 1), ("rule_index", 1)],
        unique=True,
    ),
    IndexSpec(
        collection="flow_trigger_registrations",
        name="flow_trigger_registrations_flow_id",
        keys=[("flow_id", 1)],
    ),
    IndexSpec(
        collection="flow_executions",
        name="flow_executions_trigger_dedupe_key_unique",
        keys=[("trigger.dedupe_key", 1)],
        unique=True,
        sparse=True,
    ),
    IndexSpec(
        collection="flow_executions",
        name=FLOW_EXECUTIONS_ACTIVE_FLOW_DOCUMENT_INDEX,
        keys=[("flow_id", 1), ("trigger.document_id", 1)],
        unique=True,
        partial_filter=ACTIVE_FLOW_DOCUMENT_DEDUPE_PARTIAL_FILTER,
    ),
    IndexSpec(
        collection="flow_triggers",
        name="flow_triggers_flow_node_unique",
        keys=[("flow_id", 1), ("trigger_node_id", 1)],
        unique=True,
    ),
    IndexSpec(
        collection="flow_triggers",
        name="flow_triggers_org_trigger_type",
        keys=[("org_id", 1), ("trigger_type", 1)],
    ),
    IndexSpec(
        collection="flow_results",
        name="flow_results_doc_flow_unique",
        keys=[("document_id", 1), ("flow_id", 1)],
        unique=True,
    ),
    IndexSpec(
        collection="flow_results",
        name="flow_results_org_document",
        keys=[("org_id", 1), ("document_id", 1)],
    ),
    IndexSpec(
        collection="flow_results",
        name="flow_results_org_flow",
        keys=[("org_id", 1), ("flow_id", 1)],
    ),
)

DEPRECATED_INDEXES: tuple[IndexSpec, ...] = ()
