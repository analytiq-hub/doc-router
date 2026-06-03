"""
Normalize credential field payloads before JSON Schema validation.

The credentials UI submits all form values as strings; coerce to schema types.
"""

from __future__ import annotations

from typing import Any


def apply_credential_kind_defaults(
    kind: dict[str, Any], fields: dict[str, Any]
) -> dict[str, Any]:
    """Fill missing keys from ``secret_schema`` property ``default`` values (incl. hidden/runtime fields)."""

    schema = kind.get("secret_schema")
    if not isinstance(schema, dict):
        return dict(fields)
    props = schema.get("properties")
    if not isinstance(props, dict):
        return dict(fields)

    out = dict(fields)
    for name, prop in props.items():
        if not isinstance(prop, dict) or "default" not in prop:
            continue
        cur = out.get(name)
        if cur is not None and not (isinstance(cur, str) and not str(cur).strip()):
            continue
        out[name] = prop["default"]
    return out


def normalize_credential_fields_for_kind(
    kind: dict[str, Any], fields: dict[str, Any]
) -> dict[str, Any]:
    """Kind-specific field cleanup before schema validation (e.g. SharePoint tenant slug)."""

    key = str(kind.get("key") or "")
    out = dict(fields)
    if key == "microsoftSharePointOAuth2Api":
        from analytiq_data.flows.credential_runtime import normalize_sharepoint_subdomain

        raw = str(out.get("subdomain") or "").strip()
        if raw:
            out["subdomain"] = normalize_sharepoint_subdomain(raw)
    return out


def credential_validation_schema(kind: dict[str, Any]) -> dict[str, Any] | None:
    """
    Schema for create/update validation only (``flows_credentials`` create/put).

    Runtime-only secrets (e.g. ``oauthAccessToken``) are not in ``secret_schema.properties``
    but may appear in stored payloads after OAuth; we add permissive property entries
    here so ``additionalProperties: false`` does not reject merges on update. Fields that
    are both in ``properties`` (for defaults) and ``runtime_fields`` (hidden from UI), such
    as Gmail ``scope``, need no extra entry. No other code path validates decrypted
    credentials against the raw kind schema.
    """

    from analytiq_data.flows.credential_kind_registry import credential_runtime_field_names

    schema = kind.get("secret_schema")
    if not isinstance(schema, dict):
        return None
    runtime = credential_runtime_field_names(kind)
    if not runtime:
        return schema
    out = dict(schema)
    req = out.get("required")
    if isinstance(req, list):
        out["required"] = [str(r) for r in req if str(r) not in runtime]
    props = dict(out.get("properties") or {})
    for name in runtime:
        if name not in props:
            props[name] = {}
    out["properties"] = props
    return out


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
