"""
Load credential kind definitions from ``schemas/credential-kinds/*.json`` (repo root).

See ``docs/docrouter_credentials.md``.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    # analytiq_data/flows/credential_kind_registry.py → parents[4] = workspace root
    return Path(__file__).resolve().parents[4]


@lru_cache(maxsize=1)
def _loaded_kinds() -> dict[str, dict[str, Any]]:
    root = _repo_root() / "schemas" / "credential-kinds"
    out: dict[str, dict[str, Any]] = {}
    if not root.is_dir():
        logger.warning("Credential kinds directory missing: %s", root)
        return out
    for path in sorted(root.glob("*.json")):
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception as e:
            logger.warning("Skip invalid credential kind file %s: %s", path, e)
            continue
        if not isinstance(data, dict):
            continue
        key = data.get("key")
        if not isinstance(key, str) or not key.strip():
            logger.warning("Credential kind file %s missing string 'key'", path)
            continue
        out[key] = data
    return out


def list_credential_kinds() -> list[dict[str, Any]]:
    """Return all loaded credential kind documents (mutable copies)."""

    return [dict(v) for v in _loaded_kinds().values()]


def get_credential_kind(key: str) -> dict[str, Any]:
    """Return credential kind document or raise ``KeyError``."""

    k = _loaded_kinds().get(key)
    if k is None:
        raise KeyError(key)
    return dict(k)


def credential_secret_field_names(kind: dict[str, Any]) -> set[str]:
    """Return ``secret_schema`` property keys marked ``x-secret`` for a credential kind."""

    props = (kind.get("secret_schema") or {}).get("properties") or {}
    if not isinstance(props, dict):
        return set()
    names: set[str] = set()
    for name, sub in props.items():
        if isinstance(sub, dict) and sub.get("x-secret"):
            names.add(str(name))
    return names
