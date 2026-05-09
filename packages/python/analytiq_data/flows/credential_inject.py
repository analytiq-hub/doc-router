"""
Jinja helpers for credential kind ``inject`` blocks (headers, query, body).

See ``docs/docrouter_credentials.md``.
"""

from __future__ import annotations

import json
from typing import Any

from jinja2 import Environment, Undefined


def coerce_template_json_value(val: str) -> Any:
    """Interpret an inject template result as JSON when possible, else return the string."""

    s = val.strip()
    if not s:
        return ""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return val


def render_credential_inject(
    kind: dict[str, Any], fields: dict[str, Any]
) -> dict[str, dict[str, str]]:
    """
    Render templates in ``kind["inject"]`` with ``credentials=<fields>``.

    Returns dict keys ``headers``, ``query_params``, ``body`` — mapping str -> str,
    suitable for merging into HTTP requests / credential ``/test``.
    """

    inject = kind.get("inject") if isinstance(kind.get("inject"), dict) else {}
    env = Environment(undefined=Undefined)
    creds = fields

    def _render(s: str) -> str:
        return env.from_string(s).render(credentials=creds)

    out_h: dict[str, str] = {}
    for hk, hv in (inject.get("headers") or {}).items():
        if isinstance(hv, str):
            out_h[_render(str(hk))] = _render(hv)

    out_q: dict[str, str] = {}
    for qk, qv in (inject.get("query_params") or {}).items():
        if isinstance(qv, str):
            out_q[_render(str(qk))] = _render(qv)

    out_b: dict[str, str] = {}
    for bk, bv in (inject.get("body") or {}).items():
        if isinstance(bv, str):
            out_b[_render(str(bk))] = _render(bv)

    return {"headers": out_h, "query_params": out_q, "body": out_b}


def inject_body_as_json(inject_body: dict[str, str]) -> dict[str, Any]:
    """Map rendered inject body strings to JSON-friendly Python values."""

    return {k: coerce_template_json_value(v) for k, v in inject_body.items()}
