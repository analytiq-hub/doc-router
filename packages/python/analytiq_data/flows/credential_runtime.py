"""
Runtime credential refresh: OAuth2 token exchange / refresh, client-credentials,
and optional ``pre_auth`` login requests (see ``docs/docrouter_credentials.md`` §11, Gap 4).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from jinja2 import Environment, Undefined
from jose import jwt

import analytiq_data as ad

logger = logging.getLogger(__name__)

TIME_SKEW_SEC = 120.0

_ENV_SECRET = os.getenv("NEXTAUTH_SECRET")
_ALGORITHM = "HS256"
_FLOW_OAUTH_PUBLIC_ORIGIN = (
    os.getenv("FLOW_OAUTH_PUBLIC_ORIGIN")
    or os.getenv("PUBLIC_API_URL")
    or os.getenv("DOCROUTER_API_PUBLIC_ORIGIN")
    or "http://127.0.0.1:8000"
)
_NEXTAUTH_URL = os.getenv("NEXTAUTH_URL", "http://localhost:3000")


def flow_oauth_redirect_uri() -> str:
    """Registered OAuth redirect URI (authorization + token exchange must match)."""

    base = _FLOW_OAUTH_PUBLIC_ORIGIN.rstrip("/")
    return f"{base}/v0/callback/flow-oauth"


def encode_flow_oauth_state(
    organization_id: str,
    credential_id: str,
    user_id: str,
    *,
    ttl_seconds: int = 900,
) -> str:
    """Signed JWT state (tests / legacy). Browser OAuth uses opaque server-side state instead."""

    if not _ENV_SECRET:
        raise RuntimeError("NEXTAUTH_SECRET is not configured")
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": "flow_credential_oauth",
        "org": organization_id,
        "cid": credential_id,
        "uid": user_id,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(payload, _ENV_SECRET, algorithm=_ALGORITHM)


def decode_flow_oauth_state(token: str) -> dict[str, Any]:
    if not _ENV_SECRET:
        raise RuntimeError("NEXTAUTH_SECRET is not configured")
    return jwt.decode(token, _ENV_SECRET, algorithms=[_ALGORITHM])


FLOW_OAUTH_STATE_COLLECTION = "flow_oauth_states"


async def store_flow_oauth_authorization_state(
    *,
    organization_id: str,
    credential_id: str,
    user_id: str,
    oauth_grant_type: str,
    pkce_verifier: str | None = None,
    ttl_seconds: int = 900,
) -> str:
    """Store OAuth redirect context server-side; return opaque ``state`` for the authorize URL.

    The PKCE ``code_verifier`` must never be sent to the browser — only this nonce is exposed.

    ``oauth_grant_type`` must match what was selected at initiate time (``authorizationCode`` or
    ``pkce``) so the callback cannot be confused by a later edit to the credential document.
    """

    db = ad.common.get_async_db()
    coll = db[FLOW_OAUTH_STATE_COLLECTION]
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=ttl_seconds)

    for _ in range(8):
        nonce = secrets.token_urlsafe(32)
        doc: dict[str, Any] = {
            "_id": nonce,
            "organization_id": organization_id,
            "credential_id": credential_id,
            "user_id": user_id,
            "grant_type": oauth_grant_type,
            "pkce_verifier": pkce_verifier,
            "expires_at": expires_at,
        }
        try:
            await coll.insert_one(doc)
            return nonce
        except DuplicateKeyError:
            continue
    raise RuntimeError("Could not allocate OAuth state nonce")


async def consume_flow_oauth_authorization_state(
    state_nonce: str | None,
) -> dict[str, Any] | None:
    """Delete and return pending OAuth state if unexpired (single-use)."""

    if not state_nonce or not isinstance(state_nonce, str):
        return None
    db = ad.common.get_async_db()
    coll = db[FLOW_OAUTH_STATE_COLLECTION]
    now = datetime.now(UTC)
    row = await coll.find_one_and_delete(
        {"_id": state_nonce.strip(), "expires_at": {"$gt": now}},
    )
    return dict(row) if row else None


def _get_json_path(obj: Any, path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _jinja_env() -> Environment:
    return Environment(undefined=Undefined)


def _render_pre_auth_template(s: str, fields: dict[str, Any]) -> str:
    return _jinja_env().from_string(str(s)).render(credentials=fields)


def _render_mapping_templates(d: dict[str, Any], fields: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        if isinstance(v, str):
            out[_render_pre_auth_template(str(k), fields)] = _render_pre_auth_template(v, fields)
        else:
            out[str(k)] = json.dumps(v)
    return out


async def _http_pre_auth_request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: Any,
) -> dict[str, Any]:
    await ad.flows.validate_http_url_allowed_async(url, purpose="Credential pre_auth request")
    kw: dict[str, Any] = {}
    if body is not None:
        ct = (headers.get("Content-Type") or "").lower()
        if isinstance(body, dict) and "application/x-www-form-urlencoded" in ct:
            kw["data"] = body
        elif isinstance(body, dict):
            kw["json"] = body
        elif isinstance(body, str):
            kw["content"] = body.encode()
        else:
            kw["json"] = body
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.request(method.upper(), url, headers=headers or None, **kw)
    try:
        data = resp.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if resp.status_code >= 400:
        raise RuntimeError(f"pre_auth HTTP {resp.status_code}: {resp.text[:500]}")
    return data


async def maybe_run_pre_auth(
    kind: dict[str, Any], fields: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Run ``pre_auth`` when access token is missing or expired."""

    pa = kind.get("pre_auth")
    if not isinstance(pa, dict):
        return fields, False

    access_key = str(pa.get("access_token_field") or "oauthAccessToken")
    exp_key = str(pa.get("expires_at_field") or "oauthExpiresAt")
    token_path = str(pa.get("token_json_path") or "access_token")
    exp_in_path = pa.get("expires_in_json_path")

    tok = fields.get(access_key)
    exp_at = fields.get(exp_key)
    need = False
    if not tok:
        need = True
    elif exp_at is not None:
        try:
            if time.time() >= float(exp_at) - TIME_SKEW_SEC:
                need = True
        except (TypeError, ValueError):
            pass

    if not need:
        return fields, False

    method = str(pa.get("method") or "POST").upper()
    url_tmpl = str(pa.get("url") or "").strip()
    if not url_tmpl:
        logger.warning("pre_auth missing url for kind %s", kind.get("key"))
        return fields, False

    url = _render_pre_auth_template(url_tmpl, fields)
    hdr_raw = pa.get("headers") if isinstance(pa.get("headers"), dict) else {}
    headers = _render_mapping_templates(hdr_raw, fields)
    body_raw = pa.get("body")
    body: Any = None
    if isinstance(body_raw, dict):
        rendered: dict[str, Any] = {}
        for bk, bv in body_raw.items():
            rk = _render_pre_auth_template(str(bk), fields)
            if isinstance(bv, str):
                rendered[rk] = _render_pre_auth_template(bv, fields)
            else:
                rendered[rk] = bv
        body = rendered
    elif body_raw is not None:
        body = _render_pre_auth_template(str(body_raw), fields)

    try:
        resp_json = await _http_pre_auth_request(method, url, headers, body)
    except Exception as e:
        logger.warning("pre_auth failed for kind %s: %s", kind.get("key"), e)
        return fields, False

    token_val = _get_json_path(resp_json, token_path)
    if token_val is None:
        logger.warning("pre_auth response missing token at %s", token_path)
        return fields, False

    out = dict(fields)
    out[access_key] = str(token_val)

    if exp_in_path:
        raw_exp = _get_json_path(resp_json, str(exp_in_path))
        try:
            sec = float(raw_exp)
            out[exp_key] = time.time() + sec
        except (TypeError, ValueError):
            pass

    return out, True


def _grant_type(fields: dict[str, Any]) -> str:
    return str(fields.get("grantType") or "authorizationCode")


def generate_pkce_code_verifier() -> str:
    """RFC 7636 ``code_verifier`` (high-entropy, URL-safe; 43 chars from 32 bytes)."""

    return secrets.token_urlsafe(32)


def pkce_code_challenge_s256(code_verifier: str) -> str:
    """RFC 7636 ``code_challenge`` for ``code_challenge_method=S256``."""

    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


async def _oauth_token_post(
    token_url: str,
    body: dict[str, str],
    *,
    extra_headers: dict[str, str] | None = None,
    auth_basic: tuple[str, str] | None = None,
) -> dict[str, Any]:
    await ad.flows.validate_http_url_allowed_async(token_url, purpose="OAuth2 token request")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if extra_headers:
        headers.update(extra_headers)
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            token_url,
            data=body,
            headers=headers,
            auth=auth_basic,
        )
    try:
        data = resp.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if resp.status_code >= 400:
        raise RuntimeError(f"OAuth token HTTP {resp.status_code}: {resp.text[:500]}")
    return data


async def maybe_refresh_oauth_tokens(
    kind: dict[str, Any], fields: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Refresh / obtain OAuth2 tokens for client-credentials and refresh flows."""

    mode = str(kind.get("auth_mode") or "")
    if "oauth2" not in mode.lower():
        return fields, False

    gt = _grant_type(fields)
    token_url = str(fields.get("accessTokenUrl") or "").strip()
    if not token_url:
        return fields, False

    client_id = str(fields.get("clientId") or "")
    client_secret = str(fields.get("clientSecret") or "")

    out = dict(fields)
    changed = False

    if gt == "clientCredentials":
        exp = out.get("oauthExpiresAt")
        tok = out.get("oauthAccessToken")
        need = not tok
        if exp is not None and not need:
            try:
                if time.time() >= float(exp) - TIME_SKEW_SEC:
                    need = True
            except (TypeError, ValueError):
                pass
        if not need:
            return out, False

        body = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        scope = str(fields.get("scope") or "").strip()
        if scope:
            body["scope"] = scope
        try:
            data = await _oauth_token_post(token_url, body)
        except Exception as e:
            logger.warning("client_credentials failed for kind %s: %s", kind.get("key"), e)
            return fields, False

        at = data.get("access_token")
        if at:
            out["oauthAccessToken"] = str(at)
            changed = True
        ei = data.get("expires_in")
        if ei is not None:
            try:
                out["oauthExpiresAt"] = time.time() + float(ei)
                changed = True
            except (TypeError, ValueError):
                pass
        return out, changed

    if gt != "authorizationCode":
        return fields, False

    exp = out.get("oauthExpiresAt")
    rt = out.get("oauthRefreshToken")
    at = out.get("oauthAccessToken")
    need_refresh = False
    if rt and exp is not None:
        try:
            if time.time() >= float(exp) - TIME_SKEW_SEC:
                need_refresh = True
        except (TypeError, ValueError):
            need_refresh = False
    elif rt and at and exp is None:
        need_refresh = False

    if not need_refresh or not rt:
        return fields, False

    body = {
        "grant_type": "refresh_token",
        "refresh_token": str(rt),
        "client_id": client_id,
        "client_secret": client_secret,
    }
    try:
        data = await _oauth_token_post(token_url, body)
    except Exception as e:
        logger.warning("oauth refresh failed for kind %s: %s", kind.get("key"), e)
        return fields, False

    nat = data.get("access_token")
    if nat:
        out["oauthAccessToken"] = str(nat)
        changed = True
    nrt = data.get("refresh_token")
    if nrt:
        out["oauthRefreshToken"] = str(nrt)
        changed = True
    ei = data.get("expires_in")
    if ei is not None:
        try:
            out["oauthExpiresAt"] = time.time() + float(ei)
            changed = True
        except (TypeError, ValueError):
            pass
    return out, changed


async def persist_credential_fields(
    organization_id: str,
    credential_oid: ObjectId,
    fields: dict[str, Any],
    *,
    updated_by: str,
) -> None:
    db = ad.common.get_async_db()
    encrypted = ad.crypto.encrypt_secret(json.dumps(fields))
    now = datetime.now(UTC)
    await db.credentials.update_one(
        {"_id": credential_oid, "organization_id": organization_id},
        {"$set": {"encrypted_payload": encrypted, "updated_at": now, "updated_by": updated_by}},
    )


async def apply_runtime_credential_updates(
    organization_id: str,
    credential_id: str,
    kind: dict[str, Any],
    fields: dict[str, Any],
) -> dict[str, Any]:
    """
    Apply pre_auth and OAuth token refresh; persist when changed.

    Returns the field dict to use for injection (possibly refreshed).
    """

    if not fields:
        return fields

    try:
        oid = ObjectId(credential_id)
    except Exception:
        return fields

    working = dict(fields)
    changed = False

    working, ch = await maybe_run_pre_auth(kind, working)
    changed = changed or ch

    working, ch2 = await maybe_refresh_oauth_tokens(kind, working)
    changed = changed or ch2

    if changed:
        await persist_credential_fields(
            organization_id, oid, working, updated_by="credential_runtime"
        )
    return working


async def exchange_authorization_code(
    organization_id: str,
    credential_id: str,
    fields: dict[str, Any],
    authorization_code: str,
    *,
    pkce_verifier: str | None = None,
) -> dict[str, Any]:
    """OAuth2 authorization-code exchange (browser callback)."""

    token_url = str(fields.get("accessTokenUrl") or "").strip()
    if not token_url:
        raise RuntimeError("accessTokenUrl missing")
    redirect_uri = flow_oauth_redirect_uri()
    body: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": redirect_uri,
        "client_id": str(fields.get("clientId") or ""),
        "client_secret": str(fields.get("clientSecret") or ""),
    }
    if pkce_verifier:
        body["code_verifier"] = pkce_verifier
    data = await _oauth_token_post(token_url, body)

    at_raw = data.get("access_token")
    if not at_raw:
        bits: list[str] = []
        for key in ("error", "error_description"):
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                bits.append(f"{key}={v.strip()[:300]}")
        extra = (" (" + "; ".join(bits) + ")") if bits else ""
        if not extra and data:
            extra = f": {json.dumps(data)[:400]}"
        raise RuntimeError(f"OAuth token response missing access_token{extra}")

    out = dict(fields)
    out["oauthAccessToken"] = str(at_raw)
    rt = data.get("refresh_token")
    if rt:
        out["oauthRefreshToken"] = str(rt)
    ei = data.get("expires_in")
    if ei is not None:
        try:
            out["oauthExpiresAt"] = time.time() + float(ei)
        except (TypeError, ValueError):
            pass

    oid = ObjectId(credential_id)
    await persist_credential_fields(
        organization_id, oid, out, updated_by="oauth_callback"
    )
    return out


def oauth_callback_redirect_success(organization_id: str, credential_id: str) -> str:
    from urllib.parse import quote

    base = _NEXTAUTH_URL.rstrip("/")
    cid = quote(str(credential_id), safe="")
    return (
        f"{base}/orgs/{organization_id}/flows?tab=credentials&flow_oauth=success"
        f"&flow_oauth_credential_id={cid}"
    )


def oauth_callback_redirect_error(
    organization_id: str, message: str, *, credential_id: str | None = None
) -> str:
    from urllib.parse import quote

    base = _NEXTAUTH_URL.rstrip("/")
    qs = (
        f"tab=credentials&flow_oauth=error&flow_oauth_detail={quote(message[:300])}"
    )
    if credential_id:
        qs += f"&flow_oauth_credential_id={quote(str(credential_id), safe='')}"
    return f"{base}/orgs/{organization_id}/flows?{qs}"


def oauth_callback_redirect_error_generic(message: str) -> str:
    """When ``organization_id`` is not yet known (invalid state, provider error)."""

    from urllib.parse import quote

    base = _NEXTAUTH_URL.rstrip("/")
    return f"{base}/?flow_oauth=error&flow_oauth_detail={quote(message[:300])}"


def build_oauth_authorization_url(
    fields: dict[str, Any],
    state: str,
    *,
    pkce_code_challenge: str | None = None,
) -> str:
    """Query-string for ``response_type=code`` OAuth2 authorization redirect."""

    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    auth_url = str(fields.get("authUrl") or "").strip()
    if not auth_url:
        raise RuntimeError("authUrl missing")

    auth_parts = urlparse(auth_url)
    merged: dict[str, str] = {}
    if auth_parts.query:
        for qk, qv in parse_qsl(auth_parts.query, keep_blank_values=True):
            merged[qk] = qv

    # Never allow authQueryParameters JSON to override protocol-critical / CSRF parameters.
    _locked_canonical = frozenset(
        {
            "redirect_uri",
            "state",
            "response_type",
            "client_id",
            "code_challenge",
            "code_challenge_method",
        }
    )
    aqp = fields.get("authQueryParameters")
    if isinstance(aqp, str) and aqp.strip():
        extra_pairs: dict[str, str] = {}
        raw = aqp.strip()
        if raw.startswith("{"):
            try:
                parsed_json = json.loads(raw)
                if isinstance(parsed_json, dict):
                    extra_pairs = {str(k): str(v) for k, v in parsed_json.items()}
            except json.JSONDecodeError:
                logger.warning("authQueryParameters is not valid JSON; ignoring")
        else:
            for qk, qv in parse_qsl(raw, keep_blank_values=True):
                extra_pairs[str(qk)] = str(qv)
        for k, v in extra_pairs.items():
            if k.lower() in _locked_canonical:
                logger.warning(
                    "Ignoring authQueryParameters key %r (reserved for OAuth redirect safety)",
                    k,
                )
                continue
            merged[k] = v

    merged["response_type"] = "code"
    merged["client_id"] = str(fields.get("clientId") or "")
    merged["redirect_uri"] = flow_oauth_redirect_uri()
    merged["state"] = state

    if pkce_code_challenge:
        merged["code_challenge"] = pkce_code_challenge
        merged["code_challenge_method"] = "S256"

    scope = str(fields.get("scope") or "").strip()
    if scope:
        merged["scope"] = scope

    new_query = urlencode(merged)
    return urlunparse(
        (
            auth_parts.scheme,
            auth_parts.netloc,
            auth_parts.path,
            auth_parts.params,
            new_query,
            auth_parts.fragment,
        )
    )
