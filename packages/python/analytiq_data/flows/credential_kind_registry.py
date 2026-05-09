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


def _merge_secret_schema(
    base: dict[str, Any] | None, overlay: dict[str, Any] | None
) -> dict[str, Any]:
    b = base or {}
    o = overlay or {}
    bp = dict(b.get("properties") or {})
    op = dict(o.get("properties") or {})
    merged_p = {**bp, **op}
    br = set(b.get("required") or [])
    orq = set(o.get("required") or [])
    merged_req = sorted((br | orq) & set(merged_p.keys()))
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": merged_p,
        "required": merged_req,
    }


def _merge_inject_section(
    base: dict[str, Any] | None, overlay: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not base and not overlay:
        return None
    b = base or {}
    o = overlay or {}
    headers = {**(b.get("headers") or {}), **(o.get("headers") or {})}
    qp = {**(b.get("query_params") or {}), **(o.get("query_params") or {})}
    body = {**(b.get("body") or {}), **(o.get("body") or {})}
    out: dict[str, Any] = {}
    if headers:
        out["headers"] = headers
    if qp:
        out["query_params"] = qp
    if body:
        out["body"] = body
    return out or None


def _merge_runtime_fields(a: list[str] | None, b: list[str] | None) -> list[str] | None:
    seq = list(a or []) + list(b or [])
    if not seq:
        return None
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _merge_two_kind_documents(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge ``overlay`` onto ``base`` (DocRouter credential kind JSON)."""

    out = dict(base)
    out["key"] = overlay.get("key", base.get("key"))
    out["display_name"] = overlay.get("display_name", base.get("display_name"))
    out["auth_mode"] = overlay.get("auth_mode", base.get("auth_mode"))
    out["secret_schema"] = _merge_secret_schema(
        base.get("secret_schema") if isinstance(base.get("secret_schema"), dict) else None,
        overlay.get("secret_schema") if isinstance(overlay.get("secret_schema"), dict) else None,
    )
    inj = _merge_inject_section(
        base.get("inject") if isinstance(base.get("inject"), dict) else None,
        overlay.get("inject") if isinstance(overlay.get("inject"), dict) else None,
    )
    if inj:
        out["inject"] = inj
    elif "inject" in out:
        del out["inject"]

    bt = base.get("test_request") if isinstance(base.get("test_request"), dict) else None
    ot = overlay.get("test_request") if isinstance(overlay.get("test_request"), dict) else None
    if ot:
        out["test_request"] = dict(ot)
    elif bt and not ot:
        out["test_request"] = dict(bt)

    rf = _merge_runtime_fields(
        base.get("runtime_fields") if isinstance(base.get("runtime_fields"), list) else None,
        overlay.get("runtime_fields") if isinstance(overlay.get("runtime_fields"), list) else None,
    )
    if rf:
        out["runtime_fields"] = rf
    elif "runtime_fields" in out:
        del out["runtime_fields"]

    bpa = base.get("pre_auth") if isinstance(base.get("pre_auth"), dict) else None
    opa = overlay.get("pre_auth") if isinstance(overlay.get("pre_auth"), dict) else None
    if opa:
        out["pre_auth"] = dict(opa)
    elif bpa:
        out["pre_auth"] = dict(bpa)
    elif "pre_auth" in out:
        del out["pre_auth"]

    exp = bool(base.get("experimental")) or bool(overlay.get("experimental"))
    if exp:
        out["experimental"] = True
    else:
        out.pop("experimental", None)

    return out


def _resolve_kind_with_extends(
    key: str,
    store: dict[str, dict[str, Any]],
    path: tuple[str, ...],
) -> dict[str, Any]:
    """Resolve ``extends`` chains. ``path`` is the ordered stack of kinds entered on this branch."""

    raw = store.get(key)
    if raw is None:
        raise KeyError(key)
    if key in path:
        start = path.index(key)
        cycle_keys = path[start:] + (key,)
        chain = " -> ".join(cycle_keys)
        raise ValueError(f"circular credential kind extends: {chain}")

    branch = path + (key,)

    bases: list[str] = []
    ext = raw.get("extends")
    if isinstance(ext, str):
        bases = [ext]
    elif isinstance(ext, list):
        bases = [str(x) for x in ext if isinstance(x, str)]

    merged: dict[str, Any] | None = None
    for b in bases:
        parent = _resolve_kind_with_extends(b, store, branch)
        merged = parent if merged is None else _merge_two_kind_documents(merged, parent)

    overlay = dict(raw)
    overlay.pop("extends", None)
    if merged is None:
        out = overlay
    else:
        out = _merge_two_kind_documents(merged, overlay)
    return out


def _repo_root() -> Path:
    # analytiq_data/flows/credential_kind_registry.py → parents[4] = workspace root
    return Path(__file__).resolve().parents[4]


def _read_credential_kind_store_from_disk() -> dict[str, dict[str, Any]]:
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


@lru_cache(maxsize=1)
def _credential_kinds_bundle() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Load JSON once and resolve ``extends`` once per process (until cache clear).

    Returns ``(raw_store, resolved_by_key)``. Only kinds that resolve cleanly appear in
    ``resolved_by_key`` (same as ``list_credential_kinds`` skipping broken kinds).
    """

    store = _read_credential_kind_store_from_disk()
    resolved: dict[str, dict[str, Any]] = {}
    for k in sorted(store.keys()):
        try:
            resolved[k] = _resolve_kind_with_extends(k, store, ())
        except (ValueError, KeyError) as e:
            logger.warning("Skip credential kind %s: %s", k, e)
    return store, resolved


def _loaded_kinds() -> dict[str, dict[str, Any]]:
    """Raw credential kind JSON keyed by kind ``key`` (cached via ``_credential_kinds_bundle``)."""

    return _credential_kinds_bundle()[0]


def list_credential_kinds() -> list[dict[str, Any]]:
    """Return all loaded credential kind documents (mutable copies, ``extends`` resolved)."""

    _, resolved = _credential_kinds_bundle()
    return [dict(resolved[k]) for k in sorted(resolved.keys())]


def get_credential_kind(key: str) -> dict[str, Any]:
    """Return credential kind document or raise ``KeyError`` (``extends`` merged)."""

    store, resolved = _credential_kinds_bundle()
    if key not in store:
        raise KeyError(key)
    if key in resolved:
        return dict(resolved[key])
    return dict(_resolve_kind_with_extends(key, store, ()))


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
