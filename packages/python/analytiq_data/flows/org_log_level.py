"""Organization flow execution log level (``organizations.flow_log_level``)."""

from __future__ import annotations

from typing import Any, Literal

from bson import ObjectId

FlowLogLevel = Literal["ERROR", "INFO", "TRACE"]

DEFAULT_FLOW_LOG_LEVEL: FlowLogLevel = "ERROR"
_VALID: frozenset[str] = frozenset({"ERROR", "INFO", "TRACE"})

# Map trace event levels → numeric rank (lower = more severe).
_EVENT_RANK: dict[str, int] = {
    "error": 0,
    "warn": 1,
    "info": 2,
    "debug": 3,
}

# Max event rank stored per org setting (inclusive).
_ORG_MAX_EVENT_RANK: dict[str, int] = {
    "ERROR": 0,
    "INFO": 2,
    "TRACE": 3,
}


def normalize_flow_log_level(value: Any) -> FlowLogLevel:
    if isinstance(value, str):
        upper = value.strip().upper()
        if upper in _VALID:
            return upper  # type: ignore[return-value]
    return DEFAULT_FLOW_LOG_LEVEL


def flow_log_level_includes(org_level: Any, event_level: str) -> bool:
    """Return whether ``event_level`` should be recorded for this org setting."""

    org = normalize_flow_log_level(org_level)
    ev = (event_level or "info").lower()
    rank = _EVENT_RANK.get(ev, 2)
    return rank <= _ORG_MAX_EVENT_RANK[org]


async def fetch_org_flow_log_level(db, organization_id: str) -> FlowLogLevel:
    try:
        oid = ObjectId(organization_id)
    except Exception:
        return DEFAULT_FLOW_LOG_LEVEL
    doc = await db.organizations.find_one({"_id": oid}, {"flow_log_level": 1})
    if not doc:
        return DEFAULT_FLOW_LOG_LEVEL
    return normalize_flow_log_level(doc.get("flow_log_level"))
