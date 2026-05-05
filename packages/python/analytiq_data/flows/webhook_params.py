"""
Helpers for ``flows.trigger.webhook`` inbound handling (method/IP/bot guards, revision params).

Semantics follow the sibling-reference Webhook trigger (HTTP method filtering, whitelist, bots,
raw body, synchronous response knobs) adapted to DocRouter routing by ``webhook_id``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from starlette.requests import Request

logger = logging.getLogger(__name__)

_WEBHOOK_TYPE = "flows.trigger.webhook"
_KNOWN_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"})

_BOT_UA_PAT = re.compile(
    r"bot|crawler|spider|slackbot|facebookexternalhit|linkedinbot|"
    r"discordbot|whatsapp|telegram|preview|gptbot|anthropic-ai|google-other",
    re.I,
)


def extract_webhook_params_from_revision(revision: dict[str, Any] | None) -> dict[str, Any]:
    """Return merged ``parameters`` for the first webhook trigger node in ``revision``, or ``{}``."""

    if not revision or not isinstance(revision, dict):
        return {}
    nodes_any = revision.get("nodes") or []
    if not isinstance(nodes_any, list):
        return {}
    for n_any in nodes_any:
        if not isinstance(n_any, dict):
            continue
        if n_any.get("type") != _WEBHOOK_TYPE:
            continue
        p_any = n_any.get("parameters")
        return dict(p_any) if isinstance(p_any, dict) else {}
    return {}


def allowed_http_methods_snapshot(params: dict[str, Any]) -> frozenset[str] | None:
    """
    Allowed HTTP verbs for this webhook configuration.

    ``None`` means all methods handled by the route are permitted (backward compatible).
    """

    mul = params.get("multiple_methods")
    if mul is True or mul == "true":
        raw_csv = params.get("allowed_methods")
        csv = raw_csv.strip() if isinstance(raw_csv, str) else ""
        if not csv:
            return None
        out: set[str] = set()
        for seg in csv.split(","):
            s = seg.strip().upper()
            if not s:
                continue
            if s not in _KNOWN_METHODS:
                logger.warning("Webhook allowed_methods ignores unknown verb %r", s)
                continue
            out.add(s)
        return frozenset(out) if out else None

    m_raw = params.get("http_method")
    if not m_raw:
        return None
    m = str(m_raw).strip().upper()
    if m not in _KNOWN_METHODS:
        return None
    return frozenset({m})


def request_ip_candidates(request: Request) -> tuple[list[str], str | None]:
    """
    Addresses to evaluate for IP whitelist checks (Forwarded-Chain + direct client).

    Mirrors a minimal ``req.ips`` / ``req.ip`` style ordering.
    """

    hops: list[str] = []
    xff = request.headers.get("x-forwarded-for") or ""
    if xff.strip():
        for part in xff.split(","):
            p = part.strip()
            if p:
                hops.append(p)
    direct: str | None = None
    if request.client and request.client.host:
        direct = request.client.host.strip()
        if direct and direct not in hops:
            hops.append(direct)
    ip = hops[0] if hops else direct
    return hops, ip


def is_ip_whitelisted(whitelist_csv: str | None, hops: list[str], direct_ip: str | None) -> bool:
    """
    Substring-oriented whitelist check aligned with reference Webhook behaviour.

    Comma-separated ``whitelist_csv`` entries; empty means allow all.
    """

    if whitelist_csv is None or not str(whitelist_csv).strip():
        return True

    wl_parts = [p.strip() for p in str(whitelist_csv).split(",") if str(p).strip()]
    ips = list(hops)
    if direct_ip and direct_ip not in ips:
        ips.append(direct_ip)

    for address in wl_parts:
        if direct_ip and address in direct_ip:
            return True
        if any(address in hop for hop in ips if hop):
            return True
    return False


def user_agent_looks_like_bot(user_agent: str | None) -> bool:
    if not user_agent or not isinstance(user_agent, str):
        return False
    return bool(_BOT_UA_PAT.search(user_agent))


def merge_response_headers(params: dict[str, Any]) -> dict[str, str]:
    """Build response header mapping from ``response_headers`` name/value list."""

    hdr_out: dict[str, str] = {}
    lst = params.get("response_headers")
    if isinstance(lst, list):
        for row in lst:
            if not isinstance(row, dict):
                continue
            n = row.get("name")
            if not isinstance(n, str) or not n.strip():
                continue
            v = row.get("value")
            vs = "" if v is None else str(v)
            key = n.strip()
            lk = key.lower()
            canon = "Content-Type" if lk == "content-type" else key
            hdr_out[canon] = vs
    return hdr_out


def synchronous_http_response(exec_id: str, params: dict[str, Any]) -> tuple[int, dict[str, str], bytes | None]:
    """
    Decide status code, outgoing headers (without Content-Length), and optional body bytes.

    Non-``on_received`` modes still enqueue runs but use the default JSON acknowledgement for now.
    """

    hdr_out = merge_response_headers(params)

    mode_any = params.get("response_mode") or "on_received"

    base_payload = {"execution_id": exec_id}

    def _codes() -> int:
        rc = params.get("response_code")
        try:
            c = int(rc) if rc is not None else 200
        except (TypeError, ValueError):
            return 200
        if not (100 <= c <= 599):
            return 200
        return c

    if mode_any != "on_received":
        payload = json.dumps(base_payload).encode("utf-8")
        hdr_out.setdefault("Content-Type", "application/json")
        return 200, hdr_out, payload

    status = _codes()

    if params.get("no_response_body"):
        return status, hdr_out, None

    raw_txt_any = params.get("response_data")
    raw_txt = raw_txt_any.strip() if isinstance(raw_txt_any, str) else ""

    ctype_any = params.get("response_content_type")
    ctype = ctype_any.strip() if isinstance(ctype_any, str) else ""

    if not raw_txt:
        payload = json.dumps(base_payload).encode("utf-8")
        if ctype:
            hdr_out.setdefault("Content-Type", ctype)
        else:
            hdr_out.setdefault("Content-Type", "application/json")
        return status, hdr_out, payload

    stripped = raw_txt.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            payload = json.dumps(parsed).encode("utf-8")
            hdr_out.setdefault("Content-Type", ctype or "application/json")
            return status, hdr_out, payload
        except json.JSONDecodeError:
            logger.debug("Webhook response_data JSON parse failed; sending as plain text")

    body_bytes = stripped.encode("utf-8")
    hdr_out.setdefault("Content-Type", ctype or "text/plain; charset=utf-8")
    return status, hdr_out, body_bytes
