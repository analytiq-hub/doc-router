from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def iter_integration_parameter_tree(description: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Walk integration `properties` trees (workflow-editor parameter field layout)."""

    props = description.get("properties")
    if not isinstance(props, list):
        return
    for p in props:
        yield from _walk_property(p)


def _walk_property(p: Any) -> Iterator[dict[str, Any]]:
    if not isinstance(p, dict):
        return
    if p.get("name") is not None and p.get("type") is not None:
        yield p
    for opt in p.get("options") or []:
        if not isinstance(opt, dict):
            continue
        for inner in opt.get("values") or []:
            yield from _walk_property(inner)
    for block in p.get("values") or []:
        if isinstance(block, dict):
            for inner in block.get("values") or []:
                yield from _walk_property(inner)
    for fld in p.get("fields") or []:
        yield from _walk_property(fld)
