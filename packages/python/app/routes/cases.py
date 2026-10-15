# cases.py

import json
import logging
from datetime import datetime, UTC
from typing import Any, Optional, List, Dict

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import analytiq_data as ad
from app.auth import is_organization_admin

from app.case_http import case_error_to_http
from app.licensing_deps import require_feature
from app.org_auth import require_org_config_read, require_org_config_write, require_org_documents_read, require_org_documents_write, require_org_runs_execute
from app.models import User

logger = logging.getLogger(__name__)

cases_router = APIRouter(
    tags=["cases"],
    dependencies=[Depends(require_feature("documents"))],
)


class CaseCreate(BaseModel):
    case_id: Optional[str] = None
    display_name: Optional[str] = None
    tag_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)


class CaseUpdate(BaseModel):
    display_name: Optional[str] = None
    tag_ids: Optional[List[str]] = None
    metadata: Optional[Dict[str, str]] = None


class CaseOut(BaseModel):
    case_id: str
    display_name: str
    tag_ids: List[str]
    metadata: Dict[str, str]
    document_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime


class ListCasesResponse(BaseModel):
    cases: List[CaseOut]
    total_count: int
    skip: int


class AssignDocumentsRequest(BaseModel):
    document_ids: List[str]
    create_case_if_missing: bool = False


class CaseRunRequest(BaseModel):
    prompt_id: str


def _case_to_out(case: dict, document_count: int) -> CaseOut:
    return CaseOut(
        case_id=case["case_id"],
        display_name=case.get("display_name") or case["case_id"],
        tag_ids=case.get("tag_ids") or [],
        metadata=case.get("metadata") or {},
        document_count=document_count,
        created_by=case.get("created_by", ""),
        created_at=case["created_at"],
        updated_at=case["updated_at"],
    )


def _parse_metadata_search(metadata_search: str | None) -> dict[str, str] | None:
    if not metadata_search:
        return None
    from urllib.parse import unquote

    out: dict[str, str] = {}
    for pair in metadata_search.split(","):
        pair = pair.lstrip()
        decoded = unquote(pair)
        if "=" in decoded:
            key, value = decoded.split("=", 1)
            out[key.strip()] = value
    return out or None


async def _finish_case_delete_in_background(
    organization_id: str, case_id: str, cascade_documents: bool
) -> None:
    analytiq_client = ad.common.get_analytiq_client()
    try:
        await ad.common.finish_case_delete(
            analytiq_client,
            organization_id,
            case_id,
            cascade_documents=cascade_documents,
        )
    except Exception as e:
        logger.error(
            f"Case delete {organization_id}/{case_id} stopped before finishing; "
            f"delete the case again to resume: {e}"
        )


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


@cases_router.get("/v0/orgs/{organization_id}/cases", response_model=ListCasesResponse)
async def list_cases_route(
    organization_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    case_id_search: str | None = Query(
        None,
        description="Substring match on case id or display name (case-insensitive)",
    ),
    tag_ids: str | None = Query(None, description="Comma-separated tag IDs"),
    metadata_search: str | None = Query(None),
    updated_after: str | None = Query(None, description="ISO datetime; cases updated at or after"),
    updated_before: str | None = Query(None, description="ISO datetime; cases updated at or before"),
    sort: str | None = Query(None, description="JSON-encoded MUI DataGrid sortModel (array)"),
    filters: str | None = Query(None, description="JSON-encoded MUI DataGrid filterModel (object)"),
    current_user: User = Depends(require_org_documents_read),
):
    analytiq_client = ad.common.get_analytiq_client()
    tag_id_list = [t.strip() for t in tag_ids.split(",") if t.strip()] if tag_ids else None
    sort_model = None
    filter_model = None
    if sort:
        try:
            sort_model = json.loads(sort)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="Invalid sort JSON") from e
    if filters:
        try:
            filter_model = json.loads(filters)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="Invalid filters JSON") from e
    cases, total = await ad.common.list_cases(
        analytiq_client,
        organization_id,
        skip=skip,
        limit=limit,
        case_id_search=case_id_search,
        tag_ids=tag_id_list,
        metadata_search=_parse_metadata_search(metadata_search),
        updated_after=_parse_optional_datetime(updated_after),
        updated_before=_parse_optional_datetime(updated_before),
        sort_model=sort_model,
        filter_model=filter_model,
    )
    counts = await ad.common.count_documents_in_cases(
        analytiq_client, organization_id, [case["case_id"] for case in cases]
    )
    out = [_case_to_out(case, counts[case["case_id"]]) for case in cases]
    return ListCasesResponse(cases=out, total_count=total, skip=skip)


@cases_router.post("/v0/orgs/{organization_id}/cases", response_model=CaseOut)
async def create_case_route(
    organization_id: str,
    body: CaseCreate,
    current_user: User = Depends(require_org_documents_write),
):
    analytiq_client = ad.common.get_analytiq_client()
    try:
        case = await ad.common.create_case(
            analytiq_client,
            organization_id,
            case_id=body.case_id,
            display_name=body.display_name,
            tag_ids=body.tag_ids,
            metadata=body.metadata,
            created_by=current_user.user_id,
        )
    except ValueError as e:
        msg = str(e)
        if "already exists" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    count = await ad.common.count_documents_in_case(
        analytiq_client, organization_id, case["case_id"]
    )
    return _case_to_out(case, count)


@cases_router.get("/v0/orgs/{organization_id}/cases/{case_id}", response_model=CaseOut)
async def get_case_route(
    organization_id: str,
    case_id: str,
    current_user: User = Depends(require_org_documents_read),
):
    analytiq_client = ad.common.get_analytiq_client()
    try:
        ad.common.validate_case_id(case_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    case = await ad.common.get_case(analytiq_client, organization_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    count = await ad.common.count_documents_in_case(
        analytiq_client, organization_id, case_id
    )
    return _case_to_out(case, count)


@cases_router.put("/v0/orgs/{organization_id}/cases/{case_id}", response_model=CaseOut)
async def update_case_route(
    organization_id: str,
    case_id: str,
    body: CaseUpdate,
    current_user: User = Depends(require_org_documents_write),
):
    analytiq_client = ad.common.get_analytiq_client()
    try:
        ad.common.validate_case_id(case_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        updated = await ad.common.update_case(
            analytiq_client,
            organization_id,
            case_id,
            display_name=body.display_name,
            tag_ids=body.tag_ids,
            metadata=body.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not updated:
        raise HTTPException(status_code=404, detail="Case not found")
    count = await ad.common.count_documents_in_case(
        analytiq_client, organization_id, case_id
    )
    return _case_to_out(updated, count)


@cases_router.delete("/v0/orgs/{organization_id}/cases/{case_id}")
async def delete_case_route(
    organization_id: str,
    case_id: str,
    background_tasks: BackgroundTasks,
    cascade: bool = Query(
        False,
        description=(
            "Delete every document in the case (org admins only). Always returns 202 when "
            "true, including empty cases; poll GET until 404 or refresh the list."
        ),
    ),
    current_user: User = Depends(require_org_documents_write),
):
    """
    Delete a case.

    **Default:** member documents are kept; their ``case_id`` is cleared. Returns **200**
    when finished.

    **``cascade=true``:** returns **202** immediately (even for zero documents). Document
    deletion runs in a background task. Poll ``GET .../cases/{case_id}`` until **404**, or
    refresh the cases list. Call DELETE again with the same ``cascade`` value to resume after
    a crash or deploy.
    """
    if cascade and not await is_organization_admin(organization_id, current_user.user_id):
        raise HTTPException(status_code=403, detail="Only org admins can delete a case with its documents")

    analytiq_client = ad.common.get_analytiq_client()
    try:
        case_id = ad.common.validate_case_id(case_id)
        row = await ad.common.begin_case_delete(
            analytiq_client, organization_id, case_id, cascade_documents=cascade
        )
    except (ValueError, LookupError) as e:
        raise case_error_to_http(e)
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")

    if cascade:
        background_tasks.add_task(
            _finish_case_delete_in_background, organization_id, case_id, True
        )
        return JSONResponse(status_code=202, content={"message": "Case delete started"})

    await ad.common.finish_case_delete(
        analytiq_client, organization_id, case_id, cascade_documents=False
    )
    return {"message": "Case deleted"}


@cases_router.post("/v0/orgs/{organization_id}/cases/{case_id}/documents")
async def assign_documents_route(
    organization_id: str,
    case_id: str,
    body: AssignDocumentsRequest,
    current_user: User = Depends(require_org_documents_write),
):
    analytiq_client = ad.common.get_analytiq_client()
    try:
        ad.common.validate_case_id(case_id)
        await ad.common.assign_documents_to_case(
            analytiq_client,
            organization_id,
            body.document_ids,
            case_id,
            create_case_if_missing=body.create_case_if_missing,
            created_by=current_user.user_id,
        )
    except (ValueError, LookupError) as e:
        raise case_error_to_http(e)
    return {"message": "Documents assigned", "count": len(set(body.document_ids))}


@cases_router.delete(
    "/v0/orgs/{organization_id}/cases/{case_id}/documents/{document_id}"
)
async def remove_document_from_case_route(
    organization_id: str,
    case_id: str,
    document_id: str,
    current_user: User = Depends(require_org_documents_write),
):
    analytiq_client = ad.common.get_analytiq_client()
    doc = await ad.common.get_doc(analytiq_client, document_id, organization_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.get("case_id") != case_id:
        raise HTTPException(status_code=404, detail="Document not in this case")
    try:
        await ad.common.remove_documents_from_case(
            analytiq_client, organization_id, [document_id]
        )
    except LookupError as e:
        raise case_error_to_http(e)
    return {"message": "Document removed from case"}


@cases_router.post("/v0/orgs/{organization_id}/cases/{case_id}/runs")
async def start_case_llm_run_route(
    organization_id: str,
    case_id: str,
    body: CaseRunRequest,
    current_user: User = Depends(require_org_runs_execute),
):
    """Queue a case-scoped LLM run for the latest revision of ``prompt_id``."""
    analytiq_client = ad.common.get_analytiq_client()
    try:
        ad.common.validate_case_id(case_id)
        msg_id = await ad.case_llm.enqueue_case_llm_run(
            analytiq_client,
            organization_id,
            case_id,
            body.prompt_id.strip(),
        )
    except (ValueError, LookupError) as e:
        raise case_error_to_http(e)
    return JSONResponse(
        status_code=202,
        content={"message": "Case LLM run queued", "queue_message_id": msg_id},
    )


@cases_router.get("/v0/orgs/{organization_id}/cases/{case_id}/results")
async def get_case_llm_results_route(
    organization_id: str,
    case_id: str,
    prompt_id: str = Query(..., description="Stable prompt id"),
    current_user: User = Depends(require_org_documents_read),
):
    analytiq_client = ad.common.get_analytiq_client()
    try:
        ad.common.validate_case_id(case_id)
        case = await ad.common.get_case(analytiq_client, organization_id, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return await ad.case_llm.build_case_results_payload(
            analytiq_client,
            organization_id,
            case_id,
            prompt_id.strip(),
        )
    except LookupError as e:
        raise case_error_to_http(e)
