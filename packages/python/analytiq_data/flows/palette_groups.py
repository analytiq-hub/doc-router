"""Palette sections for orchestration UI (`GET …/flows/node-types` → ``palette_group``)."""

from __future__ import annotations

from typing import Any, Final

# Human labels are applied in the frontend; API uses these stable keys.
PALETTE_GROUP_KEYS: Final[tuple[str, ...]] = (
    "docrouter",
    "app",
    "flow",
    "ai",
    "core",
    "trigger",
)

_FLOW_KEYS: Final[frozenset[str]] = frozenset({"flows.branch", "flows.merge"})


def normalize_palette_group(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    s = value.strip().lower()
    return s if s in PALETTE_GROUP_KEYS else None


def resolve_palette_group(nt: Any) -> str:
    """Return a palette section key for *nt*.

    Honors optional ``palette_group`` on node classes when valid; otherwise uses a
    deterministic rule keyed on ``is_trigger`` and ``key`` so ported integrations
    and unknown builtins still land somewhere sensible without UI flags leaking
    generic ``category`` strings into the picker.
    """

    normalized = normalize_palette_group(getattr(nt, "palette_group", None))
    if normalized:
        return normalized

    key = getattr(nt, "key", "") or ""
    if getattr(nt, "is_trigger", False):
        return "trigger"
    if key.startswith("docrouter."):
        return "docrouter"
    if key in _FLOW_KEYS:
        return "flow"
    if key.startswith("flows."):
        return "core"
    return "app"
