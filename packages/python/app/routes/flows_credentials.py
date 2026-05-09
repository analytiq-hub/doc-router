"""Org-scoped flow credentials API — see ``docs/docrouter_credentials.md`` §5."""

from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from typing import Any

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.errors import DuplicateKeyError
from jsonschema import Draft7Validator
from pydantic import BaseModel

import analytiq_data as ad
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
    secret_names = ad.flows.credential_secret_field_names(kind)
    try:
        raw = doc.get("encrypted_payload")
        all_fields: dict[str, Any] = {}
        if raw:
            decrypted = ad.crypto.decrypt_token(raw)
            if decrypted:
                parsed = json.loads(decrypted)
                if isinstance(parsed, dict):
                    all_fields = parsed
    except Exception as e:
        logger.warning("credential decrypt failed %s: %s", doc.get("_id"), e)
        all_fields = {}
    public_fields = {k: v for k, v in all_fields.items() if k not in secret_names}
    ca = doc["created_at"]
    ua = doc["updated_at"]
    return CredentialHeader(
        credential_id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        kind_key=doc["kind_key"],
        name=doc["name"],
        public_fields=public_fields,
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
    _ = organization_id, current_user
    result: list[CredentialKindSummary] = []
    for kind in ad.flows.list_credential_kinds():
        schema_props = (kind.get("secret_schema") or {}).get("properties") or {}
        if not isinstance(schema_props, dict):
            schema_props = {}
        secret_names = ad.flows.credential_secret_field_names(kind)
        fields: list[dict[str, Any]] = []
        for k, v in schema_props.items():
            if not isinstance(v, dict):
                continue
            row = dict(v)
            row.pop("x-secret", None)
            fields.append({"name": k, **row, "is_secret": k in secret_names})
        result.append(
            CredentialKindSummary(
                key=kind["key"],
                display_name=str(kind.get("display_name") or kind["key"]),
                auth_mode=str(kind.get("auth_mode") or "custom"),
                fields=fields,
                has_test_request=bool(kind.get("test_request")),
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

    schema = kind.get("secret_schema")
    if schema:
        try:
            Draft7Validator(schema).validate(req.fields)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    norm_name = _normalize_credential_name(req.name)
    if not norm_name:
        raise HTTPException(status_code=422, detail="Credential name cannot be empty")

    encrypted = ad.crypto.encrypt_token(json.dumps(req.fields))
    now = datetime.now(UTC)
    db = ad.common.get_async_db()
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

    schema = kind.get("secret_schema")
    if schema:
        try:
            Draft7Validator(schema).validate(req.fields)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    norm_name = _normalize_credential_name(req.name)
    if not norm_name:
        raise HTTPException(status_code=422, detail="Credential name cannot be empty")
    if await _credential_name_taken(db, organization_id, norm_name, exclude_id=oid):
        raise HTTPException(status_code=409, detail=_DUPLICATE_NAME_DETAIL)

    encrypted = ad.crypto.encrypt_token(json.dumps(req.fields))
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
        fields = json.loads(ad.crypto.decrypt_token(raw)) if raw else {}
        if not isinstance(fields, dict):
            fields = {}
    except Exception as e:
        return TestCredentialResponse(ok=False, error=f"Decrypt failed: {e}")

    rend = ad.flows.render_credential_inject(kind, fields)
    headers = rend["headers"]
    qs = rend["query_params"]
    inject_body = rend["body"]

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
        return TestCredentialResponse(ok=ok, status_code=resp.status_code, error=None if ok else resp.text[:500])
    except Exception as e:
        return TestCredentialResponse(ok=False, error=str(e))
