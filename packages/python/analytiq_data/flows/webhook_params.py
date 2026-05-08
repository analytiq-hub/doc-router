"""
Helpers for ``flows.trigger.webhook`` inbound handling (method/IP/bot guards, revision params).

Semantics follow the sibling-reference Webhook trigger (HTTP method filtering, whitelist, bots,
raw body, synchronous response knobs) adapted to DocRouter routing by ``webhook_id``.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
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


def trust_forwarded_for_from_env() -> bool:
    """
    When true, ``X-Forwarded-For`` is considered alongside the TCP peer for IP allowlisting.

    Set env ``FLOW_WEBHOOK_TRUST_X_FORWARDED_FOR`` to ``1`` / ``true`` only when the app sits
    behind a **trusted** reverse proxy that sets or sanitizes this header; otherwise clients can
    spoof allowed IPs.
    """

    v = os.environ.get("FLOW_WEBHOOK_TRUST_X_FORWARDED_FOR", "")
    return v.strip().lower() in ("1", "true", "yes", "on")


def extract_webhook_params_from_revision(
    revision: dict[str, Any] | None, *, webhook_leaf: str | None = None
) -> dict[str, Any]:
    """
    Return ``parameters`` for a ``flows.trigger.webhook`` node in ``revision``.

    When ``webhook_leaf`` is set, return parameters for that leaf only; if none match, ``{}``.
    Otherwise return the **first** webhook node (backward compatible).
    """

    if not revision or not isinstance(revision, dict):
        return {}
    nodes_any = revision.get("nodes") or []
    if not isinstance(nodes_any, list):
        return {}
    want = webhook_leaf.strip() if isinstance(webhook_leaf, str) else ""

    def _iter_webhook_param_dicts():
        for n_any in nodes_any:
            if not isinstance(n_any, dict):
                continue
            if n_any.get("type") != _WEBHOOK_TYPE:
                continue
            p_any = n_any.get("parameters")
            yield dict(p_any) if isinstance(p_any, dict) else {}

    if want:
        for merged in _iter_webhook_param_dicts():
            got = str(merged.get("webhook_leaf") or "").strip()
            if got == want:
                return merged
        return {}

    for merged in _iter_webhook_param_dicts():
        return merged
    return {}


def resolve_webhook_trigger_node_id(revision: dict[str, Any] | None, webhook_leaf: str) -> str | None:
    """Return the canvas node ``id`` of the webhook trigger that owns ``webhook_leaf``."""

    lf = webhook_leaf.strip()
    if not lf or not revision or not isinstance(revision, dict):
        return None
    nodes_any = revision.get("nodes") or []
    if not isinstance(nodes_any, list):
        return None
    for n_any in nodes_any:
        if not isinstance(n_any, dict):
            continue
        if n_any.get("type") != _WEBHOOK_TYPE:
            continue
        p_any = n_any.get("parameters")
        merged = dict(p_any) if isinstance(p_any, dict) else {}
        if str(merged.get("webhook_leaf") or "").strip() != lf:
            continue
        nid = n_any.get("id")
        return str(nid) if nid is not None and str(nid).strip() else None
    return None


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


def ip_whitelist_candidates(request: Request) -> list[str]:
    """
    Connection IPs to evaluate against the webhook allowlist.

    By default only ``request.client.host`` (the immediate TCP peer) is used.

    If ``FLOW_WEBHOOK_TRUST_X_FORWARDED_FOR`` is enabled (see :func:`trust_forwarded_for_from_env`),
    ordered ``X-Forwarded-For`` hops are included first (client-left convention), then the TCP peer
    if not already listed.
    """

    direct: str | None = None
    if request.client and request.client.host:
        direct = request.client.host.strip()

    if not trust_forwarded_for_from_env():
        return [direct] if direct else []

    out: list[str] = []
    seen: set[str] = set()
    xff = request.headers.get("x-forwarded-for") or ""
    if xff.strip():
        for part in xff.split(","):
            p = part.strip()
            if p and p not in seen:
                seen.add(p)
                out.append(p)
    if direct and direct not in seen:
        out.append(direct)
    return out


def _parse_candidate_ip(raw: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        s = raw.strip()
        if "%" in s:
            s = s.split("%", 1)[0].strip()
        return ipaddress.ip_address(s)
    except ValueError:
        return None


def _rule_matches_ip(rule: str, addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    r = rule.strip()
    if not r:
        return False
    if "/" in r:
        try:
            net = ipaddress.ip_network(r, strict=False)
            return addr in net
        except ValueError:
            logger.warning("Webhook ip_whitelist ignores invalid CIDR rule %r", rule)
            return False
    try:
        return addr == ipaddress.ip_address(r.strip())
    except ValueError:
        logger.warning("Webhook ip_whitelist ignores invalid IP rule %r", rule)
        return False


def is_ip_whitelisted(whitelist_csv: str | None, candidates: list[str]) -> bool:
    """
    Return whether any ``candidates`` IP matches an allowlist rule.

    Rules are comma-separated. Each rule is either a single IPv4/IPv6 address (exact match) or a
    CIDR network (e.g. ``10.0.0.0/8``, ``2001:db8::/32``). Substring matching is not used.

    Empty or whitespace-only ``whitelist_csv`` means allow all.
    """

    if whitelist_csv is None or not str(whitelist_csv).strip():
        return True

    rules = [p.strip() for p in str(whitelist_csv).split(",") if p.strip()]
    if not rules:
        return True

    if not candidates:
        return False

    for cand_s in candidates:
        addr = _parse_candidate_ip(cand_s)
        if addr is None:
            continue
        for rule in rules:
            if _rule_matches_ip(rule, addr):
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

    Full acknowledgement options apply when ``response_mode`` is ``on_received``. Other modes still use
    this helper for fallback / short JSON envelopes (e.g. missing Respond payload).
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
