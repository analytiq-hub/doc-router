"""
Normalize credential field payloads before JSON Schema validation.

The credentials UI submits all form values as strings; coerce to schema types.
"""

from __future__ import annotations

from typing import Any


def coerce_credential_fields(
    schema: dict[str, Any] | None, fields: dict[str, Any]
) -> dict[str, Any]:
    """Coerce ``fields`` values to match ``secret_schema`` property types."""

    if not schema or not fields:
        return dict(fields or {})

    props = schema.get("properties")
    if not isinstance(props, dict):
        return dict(fields)

    out = dict(fields)
    for name, prop in props.items():
        if not isinstance(prop, dict) or name not in out:
            continue
        out[name] = _coerce_property_value(prop, out[name])
    return out


def _coerce_property_value(prop: dict[str, Any], val: Any) -> Any:
    ptype = prop.get("type")
    default = prop.get("default")

    if ptype == "boolean":
        if val is None or val == "":
            return default if isinstance(default, bool) else False
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)) and val in (0, 1):
            return bool(val)
        if isinstance(val, str):
            s = val.strip().lower()
            if s in ("true", "1", "yes", "on"):
                return True
            if s in ("false", "0", "no", "off", ""):
                return False
        return bool(val)

    if ptype == "integer":
        if val is None or val == "":
            return default if isinstance(default, int) and not isinstance(default, bool) else 0
        if isinstance(val, int) and not isinstance(val, bool):
            return val
        if isinstance(val, float):
            return int(val)
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return default if isinstance(default, int) and not isinstance(default, bool) else 0
            return int(float(s))
        return val

    if ptype == "number":
        if val is None or val == "":
            return default if isinstance(default, (int, float)) and not isinstance(default, bool) else 0.0
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return default if isinstance(default, (int, float)) and not isinstance(default, bool) else 0.0
            return float(s)
        return val

    return val


def merge_credential_fields_update(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    secret_names: frozenset[str] | set[str],
) -> dict[str, Any]:
    """Apply ``incoming`` on ``existing``; omit empty secret values so stored secrets are kept."""

    out = dict(existing)
    for key, val in incoming.items():
        if key in secret_names:
            if val is None:
                continue
            if isinstance(val, str) and not val.strip():
                continue
        out[key] = val
    return out
