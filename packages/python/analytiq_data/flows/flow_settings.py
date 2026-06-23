from __future__ import annotations

"""Flow-level settings (revision ``settings`` dict)."""

import os
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FLOW_TIMEZONE_DEFAULT = "DEFAULT"

# Instance default when ``settings.timezone`` is missing or ``DEFAULT`` (override via env).
INSTANCE_DEFAULT_TIMEZONE = os.environ.get("FLOW_INSTANCE_TIMEZONE", "UTC").strip() or "UTC"


def resolve_flow_timezone(settings: dict[str, Any] | None) -> str:
    """Return an IANA timezone name for cron evaluation."""

    settings = settings or {}
    raw = settings.get("timezone")
    if raw is None:
        return INSTANCE_DEFAULT_TIMEZONE
    token = str(raw).strip()
    if not token or token == FLOW_TIMEZONE_DEFAULT:
        return INSTANCE_DEFAULT_TIMEZONE
    return token


def validate_flow_settings(settings: dict[str, Any] | None) -> list[str]:
    """Validate flow-level settings; returns human-readable error strings."""

    settings = settings or {}
    errors: list[str] = []
    if "resume_on_restart" in settings:
        raw = settings.get("resume_on_restart")
        if raw is not None and not isinstance(raw, bool):
            errors.append("resume_on_restart must be a boolean")
    if "timezone" not in settings:
        return errors
    raw = settings.get("timezone")
    if raw is None:
        return errors
    token = str(raw).strip()
    if not token or token == FLOW_TIMEZONE_DEFAULT:
        return errors
    try:
        ZoneInfo(token)
    except ZoneInfoNotFoundError:
        errors.append(f"Invalid flow timezone {token!r} (expected IANA name or DEFAULT)")
    return errors


def normalize_flow_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Return settings with known keys normalized for persistence."""

    settings = dict(settings or {})
    if "resume_on_restart" in settings:
        settings["resume_on_restart"] = bool(settings["resume_on_restart"])
    if "timezone" in settings and settings["timezone"] is not None:
        tz = str(settings["timezone"]).strip()
        settings["timezone"] = tz or FLOW_TIMEZONE_DEFAULT
    return settings
