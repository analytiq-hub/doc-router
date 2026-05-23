from __future__ import annotations

"""Persist materialized trigger registrations for observability."""

from datetime import datetime, UTC
from typing import Any
from zoneinfo import ZoneInfo

from croniter import croniter

from .cron_exprs import TriggerScheduleSpec, next_anchored_run


def _compute_next_run_at(
    spec: TriggerScheduleSpec,
    *,
    timezone: str,
    anchor: datetime | None,
) -> datetime | None:
    now = datetime.now(UTC)
    if spec.kind == "interval" and anchor is not None and spec.interval_secs:
        return next_anchored_run(anchor, spec.interval_secs, after=now)
    if spec.kind == "cron" and spec.cron_expr:
        tz = ZoneInfo(timezone or "UTC")
        itr = croniter(spec.cron_expr, datetime.now(tz))
        nxt = itr.get_next(datetime)
        if nxt.tzinfo is None:
            return nxt.replace(tzinfo=UTC)
        return nxt.astimezone(UTC)
    return None


async def upsert_trigger_registrations(
    db,
    *,
    organization_id: str,
    flow_id: str,
    flow_revid: str,
    node_id: str,
    trigger_kind: str,
    timezone: str,
    specs: list[TriggerScheduleSpec],
    anchors: dict[int, datetime],
) -> None:
    now = datetime.now(UTC)
    for spec in specs:
        anchor = anchors.get(spec.rule_index)
        doc: dict[str, Any] = {
            "organization_id": organization_id,
            "flow_id": flow_id,
            "flow_revid": flow_revid,
            "node_id": node_id,
            "rule_index": spec.rule_index,
            "trigger_kind": trigger_kind,
            "schedule_kind": spec.kind,
            "interval_secs": spec.interval_secs,
            "cron_expr": spec.cron_expr,
            "timezone": timezone if spec.kind == "cron" else None,
            "anchor_at": anchor,
            "next_run_at": _compute_next_run_at(spec, timezone=timezone, anchor=anchor),
            "updated_at": now,
        }
        await db.flow_trigger_registrations.update_one(
            {"flow_id": flow_id, "node_id": node_id, "rule_index": spec.rule_index},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )


async def delete_trigger_registrations(db, *, flow_id: str) -> None:
    await db.flow_trigger_registrations.delete_many({"flow_id": flow_id})
