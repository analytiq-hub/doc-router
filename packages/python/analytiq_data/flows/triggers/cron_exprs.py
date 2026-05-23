from __future__ import annotations

"""Compile schedule-trigger parameters and poll times into cron expressions."""

from typing import Any

from croniter import croniter


class CronExpressionError(ValueError):
    """Raised when a schedule rule cannot be turned into a valid cron expression."""


def validate_cron_expression(expr: str) -> str:
    """Return ``expr`` if ``croniter.is_valid`` accepts it, else raise."""

    expr = (expr or "").strip()
    if not expr:
        raise CronExpressionError("Cron expression is empty")
    if not croniter.is_valid(expr):
        raise CronExpressionError(f"Invalid cron expression: {expr!r}")
    return expr


def schedule_rule_to_cron(rule: dict[str, Any]) -> str:
    """
    Convert one schedule-trigger interval entry to a five-field cron string.

    Supports ``minutes``, ``hours``, ``days``, and ``cronExpression`` (n8n Schedule Trigger subset).
    Sub-minute intervals are rejected (platform minimum is one minute).
    """

    field = (rule.get("field") or "days").strip()
    if field == "minutes":
        n = int(rule.get("minutesInterval") or 1)
        if n < 1 or n > 59:
            raise CronExpressionError("minutesInterval must be between 1 and 59")
        return f"*/{n} * * * *"
    if field == "hours":
        n = int(rule.get("hoursInterval") or 1)
        if n < 1 or n > 23:
            raise CronExpressionError("hoursInterval must be between 1 and 23")
        return f"0 */{n} * * *"
    if field == "days":
        n = int(rule.get("daysInterval") or 1)
        if n < 1 or n > 31:
            raise CronExpressionError("daysInterval must be between 1 and 31")
        return f"0 0 */{n} * *"
    if field == "cronExpression":
        return validate_cron_expression(str(rule.get("cronExpression") or ""))
    raise CronExpressionError(f"Unsupported schedule interval field: {field!r}")


def schedule_params_to_crons(parameters: dict[str, Any]) -> list[str]:
    """Extract cron expressions from ``flows.trigger.schedule`` node parameters."""

    rule_block = parameters.get("rule") or {}
    intervals = rule_block.get("interval") or []
    if not isinstance(intervals, list) or not intervals:
        raise CronExpressionError("Schedule trigger requires at least one interval rule")
    crons: list[str] = []
    for entry in intervals:
        if not isinstance(entry, dict):
            continue
        crons.append(schedule_rule_to_cron(entry))
    if not crons:
        raise CronExpressionError("Schedule trigger has no valid interval rules")
    return crons


def poll_times_to_crons(poll_times: dict[str, Any] | None) -> list[str]:
    """
    Convert platform ``poll_times`` structure to cron expressions.

    Default matches n8n ``everyMinute``: ``{"item": [{"mode": "everyMinute"}]}``.
    """

    items = (poll_times or {}).get("item") or [{"mode": "everyMinute"}]
    if not isinstance(items, list):
        items = [{"mode": "everyMinute"}]
    crons: list[str] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        mode = (entry.get("mode") or "everyMinute").strip()
        if mode == "everyMinute":
            crons.append("* * * * *")
        elif mode == "everyHour":
            crons.append("0 * * * *")
        elif mode == "everyDay":
            crons.append("0 0 * * *")
        elif mode == "custom":
            crons.append(validate_cron_expression(str(entry.get("cronExpression") or "")))
        else:
            raise CronExpressionError(f"Unsupported poll_times mode: {mode!r}")
    if not crons:
        crons.append("* * * * *")
    return crons
