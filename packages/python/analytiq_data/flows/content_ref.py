"""
Resolve `$content_ref` / `$content_media_type` placeholders in nested JSON-like trees.

Used by manifest loaders and declarative interpreters (see docs/docrouter_nodes.md §4.3).
Paths are package-relative; `..` and absolute paths are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_MAX_DEPTH_DEFAULT = 64

_REF_KEYS = frozenset({"$content_ref", "$content_media_type"})


class ContentRefError(ValueError):
    """Invalid path, traversal, decode error, or corrupt ref node."""


def resolve_content_refs(
    data: Any,
    package_root: Path | str,
    *,
    max_depth: int = _MAX_DEPTH_DEFAULT,
) -> Any:
    """
    Return a structure with all `$content_ref` occurrences inlined.

    * **Bare ref object** — dict whose only keys are ``$content_ref`` and optionally
      ``$content_media_type``: the dict is replaced by file contents (JSON value if plain
      JSON without Jinja markers, otherwise UTF-8 text).
    * **JSON Schema-style node** — dict with ``type`` in ``string|object|array`` and
      ``$content_ref``: ref keys removed; ``default`` set from file (text or parsed JSON).

    Loads are resolved recursively so sidecars may nest refs.
    """
    root = Path(package_root).resolve()
    if not root.is_dir():
        raise ContentRefError(f"package_root is not a directory: {root}")
    return _resolve(data, root, 0, max_depth)


def _resolve(node: Any, root: Path, depth: int, max_depth: int) -> Any:
    if depth > max_depth:
        raise ContentRefError(f"$content_ref nesting exceeded max_depth={max_depth}")

    if isinstance(node, list):
        return [_resolve(x, root, depth + 1, max_depth) for x in node]

    if not isinstance(node, dict):
        return node

    ref = node.get("$content_ref")
    if isinstance(ref, str):
        keys = set(node.keys())
        if keys <= _REF_KEYS:
            loaded = _load_bare_ref(ref, node.get("$content_media_type"), root)
            return _resolve(loaded, root, depth + 1, max_depth)

        typ = node.get("type")
        if typ in ("string", "object", "array"):
            out = {k: v for k, v in node.items() if k not in _REF_KEYS}
            text = _read_ref_text(ref, root)
            if typ == "string":
                out["default"] = text
            else:
                try:
                    out["default"] = json.loads(text)
                except json.JSONDecodeError as e:
                    raise ContentRefError(
                        f"expected JSON for $content_ref {ref!r} (type={typ})"
                    ) from e
            return {k: _resolve(v, root, depth + 1, max_depth) for k, v in out.items()}

    return {k: _resolve(v, root, depth + 1, max_depth) for k, v in node.items()}


def _safe_ref_path(relative_path: str, root: Path) -> Path:
    if not relative_path or not isinstance(relative_path, str):
        raise ContentRefError("$content_ref must be a non-empty string")
    if relative_path.startswith(("/", "\\")) or Path(relative_path).is_absolute():
        raise ContentRefError(f"absolute paths not allowed in $content_ref: {relative_path!r}")
    norm = Path(relative_path)
    parts = norm.parts
    if ".." in parts:
        raise ContentRefError("'..' segments are forbidden in $content_ref paths")

    target = (root / norm).resolve()
    root_resolved = root.resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as e:
        raise ContentRefError(f"path escapes package root: {relative_path!r}") from e
    if not target.is_file():
        raise ContentRefError(f"$content_ref file not found: {relative_path!r}")
    return target


def _read_ref_text(relative_path: str, root: Path) -> str:
    path = _safe_ref_path(relative_path, root)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise ContentRefError(f"failed to read $content_ref {relative_path!r}: {e}") from e


def _load_bare_ref(
    relative_path: str,
    media_type: Any,
    root: Path,
) -> Any:
    text = _read_ref_text(relative_path, root)
    mt = media_type if isinstance(media_type, str) else ""

    wants_json = "json" in mt.lower() if mt else relative_path.endswith(".json")
    looks_jinja = "{{" in text or "{%" in text

    if wants_json and not looks_jinja:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    elif not wants_json and not looks_jinja and text.strip()[:1] in "[{":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    return text
