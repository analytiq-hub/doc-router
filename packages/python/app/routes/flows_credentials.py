"""Org-scoped flow credentials API — see ``docs/docrouter_credentials.md`` §5."""

from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from typing import Any

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pymongo.errors import DuplicateKeyError
from jsonschema import Draft7Validator
from pydantic import BaseModel

import analytiq_data as ad
from analytiq_data.flows.credential_fields import (
    apply_credential_kind_defaults,
    coerce_credential_fields,
    credential_validation_schema,
    merge_credential_fields_update,
)
from app.auth import get_org_user
from app.models import User

logger = logging.getLogger(__name__)

flow_credentials_router = APIRouter(tags=["credentials"])


class CredentialKindSummary(BaseModel):
    key: str
    display_name: str
    auth_mode: str
    fields: list[dict[str, Any]]
    #: True when the kind JSON defines a non-empty ``test_request`` (see credential test endpoint).
    has_test_request: bool = False
    #: OAuth2 authorization-code redirect supported (Connect in UI).
    supports_oauth_browser_flow: bool = False
    #: Redirect URI to register with the OAuth provider (when browser flow is supported).
    oauth_redirect_uri: str | None = None
    #: Kind defines ``pre_auth`` (session / token bootstrap before inject).
    has_pre_auth: bool = False
    #: Gated by organization ``experimental_features`` in list/create UI.
    experimental: bool = False


class CreateCredentialRequest(BaseModel):
    kind_key: str
    name: str
    fields: dict[str, Any]


class UpdateCredentialRequest(BaseModel):
    name: str
    fields: dict[str, Any]


class CredentialHeader(BaseModel):
    credential_id: str
    organization_id: str
    kind_key: str
    name: str
    public_fields: dict[str, Any]
    #: Secret field names that have a non-empty stored value (values are never returned).
    secret_fields_set: list[str] = []
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: str


class ListCredentialsResponse(BaseModel):
    items: list[CredentialHeader]
    total: int


class TestCredentialResponse(BaseModel):
    ok: bool
    status_code: int | None = None
    error: str | None = None


_DUPLICATE_NAME_DETAIL = "A credential with this name already exists for this organization."


def _format_credential_test_http_error(resp: httpx.Response) -> str:
    """Prefer API ``error.message`` / ``message`` over raw JSON bodies in the UI."""

    text = (resp.text or "").strip()
    if not text:
        return f"HTTP {resp.status_code}"
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                msg = err.get("message")
                if isinstance(msg, str) and msg.strip():
                    return msg.strip()[:500]
            if isinstance(err, str) and err.strip():
                return err.strip()[:500]
            msg = data.get("message")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()[:500]
    except json.JSONDecodeError:
        pass
    return text[:500]


async def _org_experimental_features_enabled(db, organization_id: str) -> bool:
    try:
        oid = ObjectId(organization_id)
    except Exception:
        return False
    doc = await db.organizations.find_one({"_id": oid}, {"experimental_features": 1})
    if not doc:
        return False
    return bool(doc.get("experimental_features"))


def _kind_supports_oauth_browser_flow(kind: dict[str, Any]) -> bool:
    """True when the kind supports the browser authorization-code / PKCE connect flow."""

    mode = str(kind.get("auth_mode") or "").lower()
    if "oauth2" not in mode:
        return False
    props = (kind.get("secret_schema") or {}).get("properties") or {}
    if not isinstance(props, dict):
        return False
    if "authUrl" not in props and "accessTokenUrl" not in props:
        return False
    if mode == "oauth2_authorization_code":
        return True
    gt = props.get("grantType")
    if isinstance(gt, dict):
        enum = gt.get("enum")
        if isinstance(enum, list) and (
            "authorizationCode" in enum or "pkce" in enum
        ):
            return True
        if gt.get("default") in ("authorizationCode", "pkce"):
            return True
    return False


class OAuthInitiateResponse(BaseModel):
    authorization_url: str


def _normalize_credential_name(name: str) -> str:
    """Trim whitespace; stored names use this form so uniqueness is predictable."""

    return name.strip()


async def _credential_name_taken(
    db,
    organization_id: str,
    name: str,
    *,
    exclude_id: ObjectId | None = None,
) -> bool:
    norm = _normalize_credential_name(name)
    if not norm:
        return False
    q: dict[str, Any] = {"organization_id": organization_id, "name": norm}
    if exclude_id is not None:
        q["_id"] = {"$ne": exclude_id}
    doc = await db.credentials.find_one(q)
    return doc is not None


def _to_header(doc: dict[str, Any], kind: dict[str, Any]) -> CredentialHeader:
    non_public = ad.flows.credential_non_public_field_names(kind)
    try:
        raw = doc.get("encrypted_payload")
        all_fields: dict[str, Any] = {}
        if raw:
            decrypted = ad.crypto.decrypt_secret(raw)
            if decrypted:
                parsed = json.loads(decrypted)
                if isinstance(parsed, dict):
                    all_fields = parsed
    except Exception as e:
        logger.warning("credential decrypt failed %s: %s", doc.get("_id"), e)
        all_fields = {}
    public_fields = {k: v for k, v in all_fields.items() if k not in non_public}
    secret_fields_set = sorted(
        k
        for k in non_public
        if k in all_fields and all_fields[k] not in (None, "")
        and not (isinstance(all_fields[k], str) and not str(all_fields[k]).strip())
    )
    ca = doc["created_at"]
    ua = doc["updated_at"]
    return CredentialHeader(
        credential_id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        kind_key=doc["kind_key"],
        name=doc["name"],
        public_fields=public_fields,
        secret_fields_set=secret_fields_set,
        created_at=ca.replace(tzinfo=UTC) if getattr(ca, "tzinfo", None) is None else ca,
        created_by=doc["created_by"],
        updated_at=ua.replace(tzinfo=UTC) if getattr(ua, "tzinfo", None) is None else ua,
        updated_by=doc["updated_by"],
    )


@flow_credentials_router.get("/v0/orgs/{organization_id}/credential-kinds")
async def list_credential_kinds(
    organization_id: str,
    current_user: User = Depends(get_org_user),
) -> list[CredentialKindSummary]:
    _ = current_user
    db = ad.common.get_async_db()
    show_exp = await _org_experimental_features_enabled(db, organization_id)
    result: list[CredentialKindSummary] = []
    for kind in ad.flows.list_credential_kinds():
        if kind.get("experimental") and not show_exp:
            continue
        schema_props = (kind.get("secret_schema") or {}).get("properties") or {}
        if not isinstance(schema_props, dict):
            schema_props = {}
        secret_names = ad.flows.credential_secret_field_names(kind)
        runtime_names = ad.flows.credential_runtime_field_names(kind)
        fields: list[dict[str, Any]] = []
        for k, v in schema_props.items():
            if not isinstance(v, dict) or k in runtime_names:
                continue
            row = dict(v)
            row.pop("x-secret", None)
            fields.append({"name": k, **row, "is_secret": k in secret_names})
        oauth_flow = _kind_supports_oauth_browser_flow(kind)
        result.append(
            CredentialKindSummary(
                key=kind["key"],
                display_name=str(kind.get("display_name") or kind["key"]),
                auth_mode=str(kind.get("auth_mode") or "custom"),
                fields=fields,
                has_test_request=bool(kind.get("test_request")),
                supports_oauth_browser_flow=oauth_flow,
                oauth_redirect_uri=ad.flows.flow_oauth_redirect_uri() if oauth_flow else None,
                has_pre_auth=isinstance(kind.get("pre_auth"), dict),
                experimental=bool(kind.get("experimental")),
            )
        )
    return result


@flow_credentials_router.post(
    "/v0/orgs/{organization_id}/credentials",
    response_model=CredentialHeader,
)
async def create_credential(
    organization_id: str,
    req: CreateCredentialRequest,
    current_user: User = Depends(get_org_user),
) -> CredentialHeader:
    try:
        kind = ad.flows.get_credential_kind(req.kind_key)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown credential kind: {req.kind_key}") from None

    db = ad.common.get_async_db()
    if kind.get("experimental") and not await _org_experimental_features_enabled(db, organization_id):
        raise HTTPException(
            status_code=403,
            detail="Experimental credential types are disabled for this organization. Enable 'Show experimental features' in organization settings.",
        )

    schema = credential_validation_schema(kind)
    fields = apply_credential_kind_defaults(kind, req.fields)
    fields = coerce_credential_fields(schema, fields)
    if schema:
        try:
            Draft7Validator(schema).validate(fields)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    norm_name = _normalize_credential_name(req.name)
    if not norm_name:
        raise HTTPException(status_code=422, detail="Credential name cannot be empty")

    encrypted = ad.crypto.encrypt_secret(json.dumps(fields))
    now = datetime.now(UTC)
    if await _credential_name_taken(db, organization_id, norm_name):
        raise HTTPException(status_code=409, detail=_DUPLICATE_NAME_DETAIL)
    try:
        res = await db.credentials.insert_one(
            {
                "organization_id": organization_id,
                "kind_key": req.kind_key,
                "name": norm_name,
                "encrypted_payload": encrypted,
                "created_at": now,
                "created_by": current_user.user_id,
                "updated_at": now,
                "updated_by": current_user.user_id,
            }
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail=_DUPLICATE_NAME_DETAIL) from None
    doc = await db.credentials.find_one({"_id": res.inserted_id})
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to read credential after insert")
    return _to_header(doc, kind)


@flow_credentials_router.get(
    "/v0/orgs/{organization_id}/credentials",
    response_model=ListCredentialsResponse,
)
async def list_credentials(
    organization_id: str,
    credential_kind: str | None = Query(None, description="Filter by kind key"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_org_user),
) -> ListCredentialsResponse:
    _ = current_user
    db = ad.common.get_async_db()
    query: dict[str, Any] = {"organization_id": organization_id}
    if credential_kind:
        query["kind_key"] = credential_kind
    total = await db.credentials.count_documents(query)
    docs = (
        await db.credentials.find(query)
        .sort("updated_at", -1)
        .skip(offset)
        .limit(limit)
        .to_list(limit)
    )
    items: list[CredentialHeader] = []
    for doc in docs:
        try:
            kind = ad.flows.get_credential_kind(doc["kind_key"])
        except KeyError:
            kind = {"secret_schema": {}, "runtime_fields": {}}
        items.append(_to_header(doc, kind))
    return ListCredentialsResponse(items=items, total=total)


@flow_credentials_router.get(
    "/v0/orgs/{organization_id}/credentials/{credential_id}",
    response_model=CredentialHeader,
)
async def get_credential(
    organization_id: str,
    credential_id: str,
    current_user: User = Depends(get_org_user),
) -> CredentialHeader:
    _ = current_user
    db = ad.common.get_async_db()
    try:
        oid = ObjectId(credential_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid credential id") from None
    doc = await db.credentials.find_one({"_id": oid, "organization_id": organization_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Credential not found")
    try:
        kind = ad.flows.get_credential_kind(doc["kind_key"])
    except KeyError:
        kind = {"secret_schema": {}}
    return _to_header(doc, kind)


@flow_credentials_router.put(
    "/v0/orgs/{organization_id}/credentials/{credential_id}",
    response_model=CredentialHeader,
)
async def update_credential(
    organization_id: str,
    credential_id: str,
    req: UpdateCredentialRequest,
    current_user: User = Depends(get_org_user),
) -> CredentialHeader:
    db = ad.common.get_async_db()
    try:
        oid = ObjectId(credential_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid credential id") from None
    doc = await db.credentials.find_one({"_id": oid, "organization_id": organization_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Credential not found")
    try:
        kind = ad.flows.get_credential_kind(doc["kind_key"])
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown credential kind: {doc.get('kind_key')}") from None

    secret_names = frozenset(ad.flows.credential_non_public_field_names(kind))
    existing_fields: dict[str, Any] = {}
    raw = doc.get("encrypted_payload")
    if raw:
        try:
            decrypted = ad.crypto.decrypt_secret(raw)
            if decrypted:
                parsed = json.loads(decrypted)
                if isinstance(parsed, dict):
                    existing_fields = parsed
        except Exception as e:
            logger.warning("credential decrypt failed on update %s: %s", oid, e)

    schema = credential_validation_schema(kind)
    merged_in = merge_credential_fields_update(
        existing_fields, req.fields, secret_names
    )
    fields = apply_credential_kind_defaults(kind, merged_in)
    fields = coerce_credential_fields(schema, fields)
    if schema:
        try:
            Draft7Validator(schema).validate(fields)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    norm_name = _normalize_credential_name(req.name)
    if not norm_name:
        raise HTTPException(status_code=422, detail="Credential name cannot be empty")
    if await _credential_name_taken(db, organization_id, norm_name, exclude_id=oid):
        raise HTTPException(status_code=409, detail=_DUPLICATE_NAME_DETAIL)

    encrypted = ad.crypto.encrypt_secret(json.dumps(fields))
    now = datetime.now(UTC)
    try:
        await db.credentials.update_one(
            {"_id": oid},
            {
                "$set": {
                    "encrypted_payload": encrypted,
                    "name": norm_name,
                    "updated_at": now,
                    "updated_by": current_user.user_id,
                }
            },
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail=_DUPLICATE_NAME_DETAIL) from None
    doc = await db.credentials.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=500, detail="Credential missing after update")
    return _to_header(doc, kind)


@flow_credentials_router.delete(
    "/v0/orgs/{organization_id}/credentials/{credential_id}",
    status_code=204,
)
async def delete_credential(
    organization_id: str,
    credential_id: str,
    current_user: User = Depends(get_org_user),
) -> None:
    _ = current_user
    db = ad.common.get_async_db()
    try:
        oid = ObjectId(credential_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid credential id") from None
    res = await db.credentials.delete_one({"_id": oid, "organization_id": organization_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Credential not found")


@flow_credentials_router.post(
    "/v0/orgs/{organization_id}/credentials/{credential_id}/test",
    response_model=TestCredentialResponse,
)
async def test_credential(
    organization_id: str,
    credential_id: str,
    current_user: User = Depends(get_org_user),
) -> TestCredentialResponse:
    _ = current_user
    from jinja2 import Environment, Undefined

    db = ad.common.get_async_db()
    try:
        oid = ObjectId(credential_id)
    except Exception:
        return TestCredentialResponse(ok=False, error="Invalid credential id")
    doc = await db.credentials.find_one({"_id": oid, "organization_id": organization_id})
    if not doc:
        return TestCredentialResponse(ok=False, error="Credential not found")
    try:
        kind = ad.flows.get_credential_kind(doc["kind_key"])
    except KeyError:
        return TestCredentialResponse(ok=False, error="Unknown credential kind")
    test_req = kind.get("test_request")
    if not test_req:
        return TestCredentialResponse(ok=True, error="No test_request defined for this kind")

    try:
        raw = doc.get("encrypted_payload")
        fields = json.loads(ad.crypto.decrypt_secret(raw)) if raw else {}
        if not isinstance(fields, dict):
            fields = {}
    except Exception as e:
        return TestCredentialResponse(ok=False, error=f"Decrypt failed: {e}")

    try:
        from analytiq_data.flows.credential_runtime import apply_runtime_credential_updates

        fields = await apply_runtime_credential_updates(
            organization_id, credential_id, kind, fields
        )
    except Exception as e:
        logger.warning("credential runtime refresh before test failed: %s", e)

    rend = ad.flows.render_credential_inject(kind, fields)
    headers = rend["headers"]
    qs = rend["query_params"]
    inject_body = rend["body"]

    inject_headers = (kind.get("inject") or {}).get("headers") or {}
    if inject_headers and not headers and "oauth2" in str(kind.get("auth_mode") or "").lower():
        if not str(fields.get("oauthAccessToken") or "").strip():
            return TestCredentialResponse(
                ok=False,
                error="Connect the account first (missing OAuth access token)",
            )

    jinja_env = Environment(undefined=Undefined)
    method = str(test_req.get("method", "GET")).upper()
    url = jinja_env.from_string(str(test_req.get("url") or "")).render(credentials=fields)
    if not url:
        return TestCredentialResponse(ok=False, error="test_request.url missing")

    try:
        await ad.flows.validate_http_url_allowed_async(url, purpose="Credential test request")
    except RuntimeError as e:
        return TestCredentialResponse(ok=False, error=str(e))

    req_kw: dict[str, Any] = {}
    if inject_body:
        req_kw["json"] = ad.flows.inject_body_as_json(inject_body)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method,
                url,
                headers=headers or None,
                params=qs or None,
                **req_kw,
            )
        ok = 200 <= resp.status_code < 300
        return TestCredentialResponse(
            ok=ok,
            status_code=resp.status_code,
            error=None if ok else _format_credential_test_http_error(resp),
        )
    except Exception as e:
        return TestCredentialResponse(ok=False, error=str(e))


@flow_credentials_router.post(
    "/v0/orgs/{organization_id}/credentials/{credential_id}/oauth/initiate",
    response_model=OAuthInitiateResponse,
)
async def oauth_initiate_flow_credential(
    organization_id: str,
    credential_id: str,
    current_user: User = Depends(get_org_user),
) -> OAuthInitiateResponse:
    from analytiq_data.flows.credential_runtime import (
        build_oauth_authorization_url,
        generate_pkce_code_verifier,
        pkce_code_challenge_s256,
        store_flow_oauth_authorization_state,
    )

    db = ad.common.get_async_db()
    try:
        oid = ObjectId(credential_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid credential id") from None
    doc = await db.credentials.find_one({"_id": oid, "organization_id": organization_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Credential not found")
    try:
        kind = ad.flows.get_credential_kind(doc["kind_key"])
    except KeyError:
        raise HTTPException(status_code=400, detail="Unknown credential kind") from None

    if not _kind_supports_oauth_browser_flow(kind):
        raise HTTPException(
            status_code=400,
            detail="This credential kind does not support OAuth browser login",
        )

    raw = doc.get("encrypted_payload")
    try:
        fields = json.loads(ad.crypto.decrypt_secret(raw)) if raw else {}
        if not isinstance(fields, dict):
            fields = {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decrypt failed: {e}") from None

    gt = str(fields.get("grantType") or "authorizationCode")
    if gt not in ("authorizationCode", "pkce"):
        raise HTTPException(
            status_code=400,
            detail="Connect is only available when Grant Type is authorization code or PKCE",
        )

    if not str(fields.get("authUrl") or "").strip():
        raise HTTPException(status_code=400, detail="Authorization URL is missing")

    from analytiq_data.flows.credential_runtime import require_oauth_client_configured

    try:
        require_oauth_client_configured(fields)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    try:
        pkce_verifier: str | None = None
        pkce_challenge: str | None = None
        if gt == "pkce":
            pkce_verifier = generate_pkce_code_verifier()
            pkce_challenge = pkce_code_challenge_s256(pkce_verifier)

        state_nonce = await store_flow_oauth_authorization_state(
            organization_id=organization_id,
            credential_id=credential_id,
            user_id=current_user.user_id,
            oauth_grant_type=gt,
            pkce_verifier=pkce_verifier,
        )
        url = build_oauth_authorization_url(
            fields, state_nonce, pkce_code_challenge=pkce_challenge
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return OAuthInitiateResponse(authorization_url=url)


@flow_credentials_router.get("/v0/callback/flow-oauth")
async def flow_oauth_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
) -> RedirectResponse:
    from analytiq_data.flows.credential_runtime import (
        consume_flow_oauth_authorization_state,
        exchange_authorization_code,
        oauth_callback_redirect_error,
        oauth_callback_redirect_error_generic,
        oauth_callback_redirect_success,
    )

    if error or error_description:
        msg = (error_description or error or "oauth_error").strip()
        return RedirectResponse(oauth_callback_redirect_error_generic(msg))

    if not code or not state:
        return RedirectResponse(oauth_callback_redirect_error_generic("missing_code_or_state"))

    pending = await consume_flow_oauth_authorization_state(state)
    if not pending:
        return RedirectResponse(
            oauth_callback_redirect_error_generic("invalid_or_expired_oauth_state")
        )

    org_id = str(pending.get("organization_id") or "")
    cred_id = str(pending.get("credential_id") or "")
    if not org_id or not cred_id:
        return RedirectResponse(
            oauth_callback_redirect_error_generic("invalid_oauth_state_payload")
        )

    db = ad.common.get_async_db()
    try:
        oid = ObjectId(cred_id)
    except Exception:
        return RedirectResponse(
            oauth_callback_redirect_error(org_id, "invalid credential", credential_id=cred_id)
        )

    doc = await db.credentials.find_one({"_id": oid, "organization_id": org_id})
    if not doc:
        return RedirectResponse(
            oauth_callback_redirect_error(
                org_id, "credential_not_found", credential_id=cred_id
            )
        )

    try:
        kind = ad.flows.get_credential_kind(doc["kind_key"])
    except KeyError:
        return RedirectResponse(
            oauth_callback_redirect_error(org_id, "unknown_kind", credential_id=cred_id)
        )

    raw = doc.get("encrypted_payload")
    try:
        fields = json.loads(ad.crypto.decrypt_secret(raw)) if raw else {}
        if not isinstance(fields, dict):
            fields = {}
    except Exception as e:
        return RedirectResponse(
            oauth_callback_redirect_error(org_id, f"decrypt: {e}", credential_id=cred_id)
        )

    pv_raw = pending.get("pkce_verifier")
    pkce_verifier_from_store: str | None = None
    if isinstance(pv_raw, str) and pv_raw.strip():
        pkce_verifier_from_store = pv_raw.strip()

    grant_type_from_pending = str(pending.get("grant_type") or "authorizationCode")
    if grant_type_from_pending not in ("authorizationCode", "pkce"):
        grant_type_from_pending = "authorizationCode"

    if grant_type_from_pending == "pkce" and not pkce_verifier_from_store:
        return RedirectResponse(
            oauth_callback_redirect_error(
                org_id,
                "OAuth PKCE verifier missing from server session",
                credential_id=cred_id,
            )
        )

    verifier_for_exchange = (
        pkce_verifier_from_store if grant_type_from_pending == "pkce" else None
    )

    try:
        await exchange_authorization_code(
            org_id, cred_id, fields, code, pkce_verifier=verifier_for_exchange
        )
    except Exception as e:
        logger.warning("oauth token exchange failed: %s", e)
        return RedirectResponse(
            oauth_callback_redirect_error(org_id, str(e), credential_id=cred_id)
        )

    return RedirectResponse(oauth_callback_redirect_success(org_id, cred_id))
