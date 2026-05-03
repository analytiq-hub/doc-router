from __future__ import annotations

"""Resolve the human-facing node title for logs and user-facing errors."""

from typing import Any


def node_name(node: dict[str, Any]) -> str:
    """
    Return the canvas ``name`` when non-empty after trim; otherwise ``id``.

    Revisions are not required to carry a non-empty ``name`` (only uniqueness is checked),
    and callers/tests may pass minimal dicts, so we avoid surfacing bare UUIDs only when a
    real name exists.
    """

    name = (node.get("name") or "").strip()
    if name:
        return name
    nid = node.get("id")
    return str(nid) if nid is not None else "?"
