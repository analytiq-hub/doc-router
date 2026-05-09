"""
Convert n8n credential JSON (from ``tools/dump_credentials.js``) to DocRouter kind JSON.

See ``docs/docrouter_credentials.md`` §10.2.
"""

from __future__ import annotations

import json
import re
from typing import Any

_UNCRED = re.compile(r"\{\{\s*\$credentials\.(\w+)\s*\}\}")

# Non-experimental kinds match ``schemas/credential-kinds/*.json`` for Basic / Bearer / Header HTTP helpers.
_NON_EXPERIMENTAL_KIND_KEYS = frozenset(
    {
        "httpBasicAuth",
        "httpBearerAuth",
        "httpHeaderAuth",
    }
)


def convert_n8n_template(s: str) -> str:
    """Map ``={{$credentials.field}}`` / ``{{$credentials.field}}`` to Jinja ``credentials.field``."""

    if not isinstance(s, str):
        return str(s)
    t = s.lstrip("=").strip()
    return _UNCRED.sub(r"{{ credentials.\1 }}", t)


def _template_mapping(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            nk = convert_n8n_template(k) if isinstance(k, str) else k
            out[str(nk)] = _template_mapping(v)
        return out
    if isinstance(obj, list):
        return [_template_mapping(x) for x in obj]
    if isinstance(obj, str):
        return convert_n8n_template(obj)
    return obj


def map_authenticate_generic(auth: dict[str, Any] | None) -> dict[str, dict[str, str]] | None:
    """Return DocRouter ``inject`` sections from n8n generic authenticate, or None."""

    if not auth or auth.get("type") != "generic":
        return None
    props = auth.get("properties")
    if not isinstance(props, dict):
        return None
    out: dict[str, dict[str, str]] = {"headers": {}, "query_params": {}, "body": {}}
    if isinstance(props.get("headers"), dict):
        out["headers"] = {str(k): str(v) for k, v in props["headers"].items()}
    if isinstance(props.get("qs"), dict):
        out["query_params"] = {str(k): str(v) for k, v in props["qs"].items()}
    if isinstance(props.get("body"), dict):
        out["body"] = {str(k): str(v) for k, v in props["body"].items()}
    # Drop empty sections for cleaner JSON
    return {k: v for k, v in out.items() if v}


def map_test_request(test: dict[str, Any] | None) -> dict[str, str] | None:
    if not test:
        return None
    req = test.get("request")
    if not isinstance(req, dict):
        return None
    base = str(req.get("baseURL") or "").rstrip("/")
    url_part = str(req.get("url") or "").strip()
    method = str(req.get("method") or "GET").upper()
    if url_part.startswith("http://") or url_part.startswith("https://"):
        full = url_part
    elif base and url_part:
        sep = "" if url_part.startswith("/") else "/"
        full = f"{base}{sep}{url_part}"
    elif base:
        full = base
    else:
        full = url_part
    if not full:
        return None
    return {"method": method, "url": full}


def infer_auth_mode(
    properties: list[dict[str, Any]],
    *,
    inject: dict[str, Any] | None,
    extends: list[str] | None,
) -> str:
    """Infer DocRouter ``auth_mode`` from n8n fields (best-effort)."""

    grant_default: str | None = None
    for p in properties:
        if not isinstance(p, dict):
            continue
        if p.get("name") == "grantType":
            d = p.get("default")
            if isinstance(d, str):
                grant_default = d
            break
    if grant_default == "authorizationCode":
        return "oauth2_authorization_code"
    if grant_default == "clientCredentials":
        return "oauth2_client_credentials"
    if grant_default == "pkce":
        return "oauth2_authorization_code"
    if extends:
        return "oauth2_authorization_code"
    if inject:
        return "api_key"
    return "custom"


_SKIP_PROP_TYPES = frozenset(
    {
        "notice",
        "collection",
        "fixedCollection",
        "json",
        "color",
        "dateTime",
        "filter",
        "resourceLocator",
    }
)


def property_to_schema_entry(
    prop: dict[str, Any],
    *,
    runtime_fields: list[str],
) -> tuple[str, dict[str, Any]] | None:
    """
    Map one n8n ``INodeProperties`` entry to JSON Schema property + side-effect ``runtime_fields``.

    Returns ``(name, schema_fragment)`` or ``None`` if skipped entirely (notice / unsupported).
    """

    name = prop.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    typ = prop.get("type")
    display = prop.get("displayName")
    title = str(display) if isinstance(display, str) else name

    if typ in _SKIP_PROP_TYPES:
        return None

    if typ == "hidden":
        runtime_fields.append(name)
        return None

    schema: dict[str, Any] = {"title": title}

    if typ == "string" or typ == "text":
        schema["type"] = "string"
    elif typ == "number":
        schema["type"] = "number"
    elif typ == "boolean":
        schema["type"] = "boolean"
    elif typ == "options":
        opts = prop.get("options")
        if not isinstance(opts, list) or not opts:
            return None
        values: list[str] = []
        for o in opts:
            if isinstance(o, dict) and "value" in o:
                values.append(str(o["value"]))
            elif isinstance(o, dict) and "name" in o:
                values.append(str(o["name"]))
        if not values:
            return None
        schema["type"] = "string"
        schema["enum"] = values
    elif typ == "multiOptions":
        opts = prop.get("options")
        if not isinstance(opts, list) or not opts:
            return None
        values = []
        for o in opts:
            if isinstance(o, dict) and "value" in o:
                values.append(str(o["value"]))
        if not values:
            return None
        schema["type"] = "array"
        schema["items"] = {"type": "string", "enum": values}
    else:
        # Unknown — omit from declarative port (caller may skip whole credential)
        raise ValueError(f"unsupported property type: {typ!r}")

    if isinstance(prop.get("description"), str):
        schema["description"] = prop["description"]

    typ_opts = prop.get("typeOptions")
    if isinstance(typ_opts, dict) and typ_opts.get("password"):
        schema["x-secret"] = True

    default = prop.get("default")
    if default is not None and typ != "multiOptions":
        schema["default"] = default

    return name, schema


def port_record_to_kind(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """
    Convert one dumped n8n credential object into a DocRouter kind document.

    Returns ``(kind_dict, error_message)``. On success ``error_message`` is None.
    """

    key = record.get("name")
    if not isinstance(key, str) or not key.strip():
        return None, "missing name"

    display_name = record.get("displayName")
    if not isinstance(display_name, str) or not display_name.strip():
        display_name = key

    props_raw = record.get("properties")
    if not isinstance(props_raw, list):
        props_raw = []

    runtime_fields: list[str] = []
    schema_props: dict[str, Any] = {}
    required_names: list[str] = []

    unsupported: list[str] = []
    for prop in props_raw:
        if not isinstance(prop, dict):
            continue
        try:
            pair = property_to_schema_entry(prop, runtime_fields=runtime_fields)
        except ValueError as e:
            unsupported.append(str(e))
            continue
        if pair is None:
            continue
        n, frag = pair
        schema_props[n] = frag
        if prop.get("required") is True:
            required_names.append(n)

    if unsupported:
        return None, "; ".join(unsupported[:3])

    auth = record.get("authenticate")
    if isinstance(auth, dict) and auth.get("type") and auth.get("type") != "generic":
        return None, f"non-generic authenticate: {auth.get('type')}"

    inject = map_authenticate_generic(auth if isinstance(auth, dict) else None)
    if inject:
        inject = _template_mapping(inject)

    test_req = map_test_request(record.get("test") if isinstance(record.get("test"), dict) else None)

    extends_list: list[str] | None = None
    extends_raw = record.get("extends")
    if isinstance(extends_raw, str):
        extends_list = [extends_raw]
    elif isinstance(extends_raw, list):
        extends_list = [str(x) for x in extends_raw if isinstance(x, str)]
    if extends_list is not None and not extends_list:
        extends_list = None

    auth_mode = infer_auth_mode(
        [p for p in props_raw if isinstance(p, dict)],
        inject=inject,
        extends=extends_list,
    )

    req_final = sorted(set(required_names) & set(schema_props.keys()))

    kind: dict[str, Any] = {
        "key": key,
        "display_name": display_name.strip(),
        "auth_mode": auth_mode,
        "secret_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": schema_props,
            "required": req_final,
        },
    }

    if extends_list:
        kind["extends"] = extends_list

    if runtime_fields:
        # Dedupe preserving order
        seen_rf: set[str] = set()
        rf_out: list[str] = []
        for x in runtime_fields:
            if x not in seen_rf:
                seen_rf.add(x)
                rf_out.append(x)
        kind["runtime_fields"] = rf_out

    if inject:
        kind["inject"] = inject

    if test_req:
        kind["test_request"] = test_req

    kind["experimental"] = key not in _NON_EXPERIMENTAL_KIND_KEYS

    return kind, None


def iter_ndjson_lines(fp: Any) -> Any:
    for line in fp:
        line = line.strip()
        if not line:
            continue
        yield json.loads(line)
