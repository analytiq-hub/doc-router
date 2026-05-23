from __future__ import annotations

"""Compile schedule-trigger and poll parameters into cron or anchored interval specs."""

from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import Any, Literal

from croniter import croniter


class CronExpressionError(ValueError):
    """Raised when a schedule rule cannot be parsed."""


@dataclass(frozen=True)
class TriggerScheduleSpec:
    """One trigger rule: fixed interval from an anchor, or wall-clock cron."""

    kind: Literal["interval", "cron"]
    rule_index: int
    interval_secs: float | None = None
    cron_expr: str | None = None


def validate_cron_expression(expr: str) -> str:
    """Return ``expr`` if ``croniter.is_valid`` accepts it, else raise."""

    expr = (expr or "").strip()
    if not expr:
        raise CronExpressionError("Cron expression is empty")
    if not croniter.is_valid(expr):
        raise CronExpressionError(f"Invalid cron expression: {expr!r}")
    return expr


def schedule_rule_to_interval_seconds(rule: dict[str, Any]) -> float | None:
    """
    Return fixed interval length in seconds for minutes/hours/days rules.

    Returns ``None`` for ``cronExpression`` (wall-clock cron semantics).
    """

    field = (rule.get("field") or "days").strip()
    if field == "minutes":
        n = int(rule.get("minutesInterval") or 1)
        if n < 1 or n > 59:
            raise CronExpressionError("minutesInterval must be between 1 and 59")
        return float(n * 60)
    if field == "hours":
        n = int(rule.get("hoursInterval") or 1)
        if n < 1 or n > 23:
            raise CronExpressionError("hoursInterval must be between 1 and 23")
        return float(n * 3600)
    if field == "days":
        n = int(rule.get("daysInterval") or 1)
        if n < 1 or n > 31:
            raise CronExpressionError("daysInterval must be between 1 and 31")
        return float(n * 86400)
    if field == "cronExpression":
        return None
    raise CronExpressionError(f"Unsupported schedule interval field: {field!r}")


def schedule_rule_to_spec(rule: dict[str, Any], rule_index: int) -> TriggerScheduleSpec:
    interval_secs = schedule_rule_to_interval_seconds(rule)
    if interval_secs is not None:
        return TriggerScheduleSpec(
            kind="interval",
            rule_index=rule_index,
            interval_secs=interval_secs,
        )
    cron_expr = validate_cron_expression(str(rule.get("cronExpression") or ""))
    return TriggerScheduleSpec(
        kind="cron",
        rule_index=rule_index,
        cron_expr=cron_expr,
    )


def schedule_params_to_specs(parameters: dict[str, Any]) -> list[TriggerScheduleSpec]:
    """Parse ``flows.trigger.schedule`` parameters into trigger schedule specs."""

    rule_block = parameters.get("rule") or {}
    intervals = rule_block.get("interval") or []
    if not isinstance(intervals, list) or not intervals:
        raise CronExpressionError("Schedule trigger requires at least one interval rule")
    specs: list[TriggerScheduleSpec] = []
    for rule_index, entry in enumerate(intervals):
        if not isinstance(entry, dict):
            continue
        specs.append(schedule_rule_to_spec(entry, rule_index))
    if not specs:
        raise CronExpressionError("Schedule trigger has no valid interval rules")
    return specs


def schedule_rule_to_cron(rule: dict[str, Any]) -> str:
    """Legacy helper: cron string for a rule (interval rules use synthetic every-minute cron)."""

    interval_secs = schedule_rule_to_interval_seconds(rule)
    if interval_secs is not None:
        return "* * * * *"
    return validate_cron_expression(str(rule.get("cronExpression") or ""))


def schedule_params_to_crons(parameters: dict[str, Any]) -> list[str]:
    """Legacy helper returning a cron string per rule (interval rules map to ``* * * * *``)."""

    return [
        spec.cron_expr if spec.kind == "cron" else "* * * * *"
        for spec in schedule_params_to_specs(parameters)
    ]


def poll_entry_to_spec(entry: dict[str, Any], rule_index: int) -> TriggerScheduleSpec:
    mode = (entry.get("mode") or "everyMinute").strip()
    if mode == "everyMinute":
        return TriggerScheduleSpec(kind="interval", rule_index=rule_index, interval_secs=60.0)
    if mode == "everyHour":
        return TriggerScheduleSpec(kind="interval", rule_index=rule_index, interval_secs=3600.0)
    if mode == "everyDay":
        return TriggerScheduleSpec(kind="interval", rule_index=rule_index, interval_secs=86400.0)
    if mode == "custom":
        cron_expr = validate_cron_expression(str(entry.get("cronExpression") or ""))
        return TriggerScheduleSpec(kind="cron", rule_index=rule_index, cron_expr=cron_expr)
    raise CronExpressionError(f"Unsupported poll_times mode: {mode!r}")


def poll_times_to_specs(poll_times: dict[str, Any] | None) -> list[TriggerScheduleSpec]:
    items = (poll_times or {}).get("item") or [{"mode": "everyMinute"}]
    if not isinstance(items, list):
        items = [{"mode": "everyMinute"}]
    specs: list[TriggerScheduleSpec] = []
    for rule_index, entry in enumerate(items):
        if not isinstance(entry, dict):
            continue
        specs.append(poll_entry_to_spec(entry, rule_index))
    if not specs:
        specs.append(poll_entry_to_spec({"mode": "everyMinute"}, 0))
    return specs


def poll_times_to_crons(poll_times: dict[str, Any] | None) -> list[str]:
    return [
        spec.cron_expr if spec.kind == "cron" else "* * * * *"
        for spec in poll_times_to_specs(poll_times)
    ]


def next_anchored_run(anchor: datetime, interval_secs: float, *, after: datetime | None = None) -> datetime:
    """Next run strictly after ``after``, aligned to ``anchor + n * interval``."""

    if after is None:
        after = datetime.now(UTC)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=UTC)
    if after.tzinfo is None:
        after = after.replace(tzinfo=UTC)
    interval = timedelta(seconds=interval_secs)
    if after <= anchor:
        return anchor + interval
    elapsed = (after - anchor).total_seconds()
    k = int(elapsed // interval_secs) + 1
    return anchor + timedelta(seconds=k * interval_secs)


def parse_schedule_anchor(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
