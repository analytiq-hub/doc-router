# cases.py

import logging
from datetime import datetime, UTC
from typing import Any, Optional, List, Dict

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import analytiq_data as ad
from app.auth import get_org_user, is_organization_admin
from app.licensing_deps import require_feature
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


def case_error_to_http(exc: Exception) -> HTTPException:
    """Map case errors (``ValueError``, ``LookupError`` codes) to HTTP errors. Shared with documents routes."""
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    code = str(exc)
    if code == "unknown_case":
        return HTTPException(status_code=400, detail="Unknown case_id")
    if code == "case_deleting":
        return HTTPException(status_code=409, detail="Case is being deleted")
    if code == "delete_mode_conflict":
        return HTTPException(
            status_code=409,
            detail="Case is already being deleted with a different cascade setting",
        )
    if code == "document_not_found":
        return HTTPException(status_code=404, detail="Document not found")
    return HTTPException(status_code=400, detail=code)


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


@cases_router.get("/v0/orgs/{organization_id}/cases", response_model=ListCasesResponse)
async def list_cases_route(
    organization_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    case_id_search: str | None = Query(None),
    tag_ids: str | None = Query(None, description="Comma-separated tag IDs"),
    metadata_search: str | None = Query(None),
    current_user: User = Depends(get_org_user),
):
    analytiq_client = ad.common.get_analytiq_client()
    tag_id_list = [t.strip() for t in tag_ids.split(",") if t.strip()] if tag_ids else None
    cases, total = await ad.common.list_cases(
        analytiq_client,
        organization_id,
        skip=skip,
        limit=limit,
        case_id_search=case_id_search,
        tag_ids=tag_id_list,
        metadata_search=_parse_metadata_search(metadata_search),
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
    current_user: User = Depends(get_org_user),
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
    current_user: User = Depends(get_org_user),
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
    current_user: User = Depends(get_org_user),
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
    cascade: bool = Query(False, description="Also delete every document in the case (org admins only)"),
    current_user: User = Depends(get_org_user),
):
    """
    Delete a case. Without ``cascade``, member documents are kept and removed from the
    case. With ``cascade``, documents are deleted in the background and the call returns
    ``202``. Deleting again resumes an interrupted delete.
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
    current_user: User = Depends(get_org_user),
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
    current_user: User = Depends(get_org_user),
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
