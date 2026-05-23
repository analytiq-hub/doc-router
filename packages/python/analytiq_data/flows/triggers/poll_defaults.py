from __future__ import annotations

"""Platform-owned defaults for poll trigger nodes."""

from typing import Any

DEFAULT_POLL_TIMES: dict[str, Any] = {"item": [{"mode": "everyMinute"}]}

POLL_TIMES_PROPERTY: dict[str, Any] = {
    "type": "object",
    "title": "Poll times",
    "description": "Platform-managed poll schedule (minimum interval: every minute).",
    "default": DEFAULT_POLL_TIMES,
    "x-ui-hidden": True,
    "properties": {
        "item": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["everyMinute", "everyHour", "everyDay", "custom"],
                        "default": "everyMinute",
                    },
                    "cronExpression": {
                        "type": "string",
                        "default": "* * * * *",
                    },
                },
                "required": ["mode"],
            },
        },
    },
    "required": ["item"],
}


def resolve_poll_times(parameters: dict[str, Any] | None) -> dict[str, Any]:
    """Return ``poll_times`` from node parameters, falling back to the platform default."""

    params = parameters or {}
    raw = params.get("poll_times")
    if isinstance(raw, dict) and raw.get("item"):
        return raw
    return dict(DEFAULT_POLL_TIMES)
