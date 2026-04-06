# ocr.py

# Standard library imports
import asyncio
import gzip
import json
import logging
from typing import Literal, Optional
from pydantic import BaseModel

# Third-party imports
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse

# Local imports
import analytiq_data as ad
from analytiq_data.aws.textract import ocr_result_blocks
from app.auth import get_org_user
from app.models import User

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
ocr_router = APIRouter(tags=["ocr"])

# OCR models
class GetOCRMetadataResponse(BaseModel):
    n_pages: int
    ocr_date: str

@ocr_router.post("/v0/orgs/{organization_id}/ocr/run/{document_id}")
async def run_ocr(
    organization_id: str,
    document_id: str,
    force: bool = Query(default=True, description="Force re-run even if OCR result exists"),
    ocr_only: bool = Query(default=False, description="Skip LLM and KB indexing after OCR completes"),
    current_user: User = Depends(get_org_user),
):
    """Re-run OCR on a document."""
    logger.info(f"run_ocr(): document_id={document_id}, force={force}, ocr_only={ocr_only}")
    analytiq_client = ad.common.get_analytiq_client()

    document = await ad.common.get_doc(
        analytiq_client, document_id, organization_id
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_name = document.get("user_file_name", "")
    if not ad.common.doc.ocr_supported(file_name):
        raise HTTPException(status_code=400, detail="Document type does not support OCR")

    if not ocr_only:
        await ad.common.doc.update_doc_state(
            analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_UPLOADED
        )
    else:
        # Skip full pipeline reset (uploaded) but leave a non-terminal state for polling
        # (e.g. after ocr_failed) before the worker picks up the job.
        await ad.common.doc.update_doc_state(
            analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_OCR_PROCESSING
        )
    await ad.queue.send_msg(
        analytiq_client, "ocr", msg={"document_id": document_id, "force": force, "ocr_only": ocr_only}
    )
    return {"status": "queued", "document_id": document_id}

@ocr_router.get("/v0/orgs/{organization_id}/ocr/download/blocks/{document_id}")
async def download_ocr_blocks(
    organization_id: str,
    document_id: str,
    format: Literal["plain", "gzip"] = Query(
        "plain",
        description="Response format: 'plain' (default, raw JSON) or 'gzip' (gzip-compressed JSON)",
    ),
    current_user: User = Depends(get_org_user),
):
    """Download OCR blocks for a document. Use format=gzip for compressed response."""
    logger.debug(f"download_ocr_blocks() start: document_id: {document_id}, format: {format}")
    analytiq_client = ad.common.get_analytiq_client()

    document = await ad.common.get_doc(
        analytiq_client, document_id, organization_id
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_name = document.get("user_file_name", "")
    if not ad.common.doc.ocr_supported(file_name):
        raise HTTPException(status_code=404, detail="OCR not supported for this document extension")

    # Get the OCR JSON data from mongodb
    ocr_json = await ad.ocr.get_ocr_json(analytiq_client, document_id)
    if ocr_json is None:
        raise HTTPException(status_code=404, detail="OCR data not found")

    # Flat list expected by clients (SDK / PDF viewer). Stored payload may be a legacy list or
    # a Textract-shaped dict with ``Blocks`` (see :func:`ocr_result_blocks`).
    blocks = ocr_result_blocks(ocr_json)

    headers = {"Cache-Control": "private, max-age=3600"}

    if format == "gzip":
        # Run CPU-bound json.dumps + gzip.compress in a thread pool so the event loop is not blocked
        def _serialize_and_compress(data: list) -> bytes:
            return gzip.compress(json.dumps(data).encode("utf-8"))

        body = await asyncio.to_thread(_serialize_and_compress, blocks)
        return Response(
            content=body,
            media_type="application/json",
            headers={**headers, "Content-Encoding": "gzip"},
        )

    return JSONResponse(content=blocks, headers=headers)

@ocr_router.get("/v0/orgs/{organization_id}/ocr/download/text/{document_id}", response_model=str)
async def download_ocr_text(
    organization_id: str,
    document_id: str,
    page_num: Optional[int] = Query(None, description="Specific page number to retrieve"),
    current_user: User = Depends(get_org_user)
):
    """Download OCR text for a document"""
    logger.debug(f"download_ocr_text() start: document_id: {document_id}, page_num: {page_num}")
    
    analytiq_client = ad.common.get_analytiq_client()
    document = await ad.common.get_doc(
        analytiq_client, document_id, organization_id
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_name = document.get("user_file_name", "")
    if not ad.common.doc.ocr_supported(file_name):
        raise HTTPException(status_code=404, detail="OCR not supported for this document extension")

    # Page number is 1-based, but the OCR text page_idx is 0-based
    page_idx = None
    if page_num is not None:
        page_idx = page_num - 1

    # Get the OCR text data from mongodb
    text = await ad.ocr.get_ocr_text(analytiq_client, document_id, page_idx)
    if text is None:
        raise HTTPException(status_code=404, detail="OCR text not found")
    
    return Response(content=text, media_type="text/plain")

@ocr_router.get("/v0/orgs/{organization_id}/ocr/download/metadata/{document_id}", response_model=GetOCRMetadataResponse)
async def get_ocr_metadata(
    organization_id: str,
    document_id: str,
    current_user: User = Depends(get_org_user)
):
    """Get OCR metadata for a document"""
    logger.debug(f"get_ocr_metadata() start: document_id: {document_id}")
    
    analytiq_client = ad.common.get_analytiq_client()
    document = await ad.common.get_doc(
        analytiq_client, document_id, organization_id
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_name = document.get("user_file_name", "")
    if not ad.common.doc.ocr_supported(file_name):
        raise HTTPException(status_code=404, detail="OCR not supported for this document extension")

    # Get the OCR metadata from mongodb
    metadata = await ad.ocr.get_ocr_metadata(analytiq_client, document_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="OCR metadata not found")
    
    return GetOCRMetadataResponse(
        n_pages=metadata["n_pages"],
        ocr_date=metadata["ocr_date"].isoformat()
    )


def _ocr_export_http_errors(exc: Exception) -> HTTPException:
    msg = str(exc)
    if isinstance(exc, ValueError):
        if "OCR data not found" in msg or "no tables in OCR" in msg:
            return HTTPException(status_code=404, detail=msg)
        return HTTPException(status_code=400, detail=msg)
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=502, detail=msg)
    return HTTPException(status_code=500, detail=msg)


@ocr_router.get("/v0/orgs/{organization_id}/ocr/export/markdown/{document_id}")
async def get_ocr_export_markdown(
    organization_id: str,
    document_id: str,
    current_user: User = Depends(get_org_user),
):
    """Return OCR linearized as Markdown (textractor), computed from stored OCR JSON."""
    logger.debug(
        f"get_ocr_export_markdown() document_id={document_id} org={organization_id}"
    )
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    document = await db.docs.find_one(
        {"_id": ObjectId(document_id), "organization_id": organization_id}
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_name = document.get("user_file_name", "")
    if not ad.common.doc.ocr_supported(file_name):
        raise HTTPException(
            status_code=404, detail="OCR not supported for this document extension"
        )

    try:
        body = await ad.ocr.export_ocr_markdown(
            analytiq_client, document_id, org_id=organization_id
        )
    except (ValueError, RuntimeError) as e:
        raise _ocr_export_http_errors(e) from e

    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Cache-Control": "private, max-age=60"},
    )


@ocr_router.get("/v0/orgs/{organization_id}/ocr/export/html/{document_id}")
async def get_ocr_export_html(
    organization_id: str,
    document_id: str,
    current_user: User = Depends(get_org_user),
):
    """Return OCR linearized as HTML (textractor), computed from stored OCR JSON."""
    logger.debug(f"get_ocr_export_html() document_id={document_id} org={organization_id}")
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    document = await db.docs.find_one(
        {"_id": ObjectId(document_id), "organization_id": organization_id}
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_name = document.get("user_file_name", "")
    if not ad.common.doc.ocr_supported(file_name):
        raise HTTPException(
            status_code=404, detail="OCR not supported for this document extension"
        )

    try:
        body = await ad.ocr.export_ocr_html(
            analytiq_client, document_id, org_id=organization_id
        )
    except (ValueError, RuntimeError) as e:
        raise _ocr_export_http_errors(e) from e

    return Response(
        content=body,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "private, max-age=60"},
    )


@ocr_router.get("/v0/orgs/{organization_id}/ocr/export/tables.xlsx/{document_id}")
async def get_ocr_export_tables_xlsx(
    organization_id: str,
    document_id: str,
    table_index: Optional[int] = Query(
        None,
        description="0-based table index; omit to export all tables (one sheet per table)",
    ),
    current_user: User = Depends(get_org_user),
):
    """Export detected table(s) to Excel (.xlsx) via textractor, from stored OCR JSON."""
    logger.debug(
        f"get_ocr_export_tables_xlsx() document_id={document_id} org={organization_id} "
        f"table_index={table_index}"
    )
    analytiq_client = ad.common.get_analytiq_client()
    db = ad.common.get_async_db(analytiq_client)
    document = await db.docs.find_one(
        {"_id": ObjectId(document_id), "organization_id": organization_id}
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_name = document.get("user_file_name", "")
    if not ad.common.doc.ocr_supported(file_name):
        raise HTTPException(
            status_code=404, detail="OCR not supported for this document extension"
        )

    try:
        body = await ad.ocr.export_ocr_tables_excel(
            analytiq_client,
            document_id,
            org_id=organization_id,
            table_index=table_index,
        )
    except (ValueError, RuntimeError) as e:
        raise _ocr_export_http_errors(e) from e

    safe_name = "".join(c for c in file_name if c.isalnum() or c in "._- ")[:80] or "document"
    if not safe_name.lower().endswith(".xlsx"):
        base = safe_name.rsplit(".", 1)[0] if "." in safe_name else safe_name
        filename = f"{base}-tables.xlsx"
    else:
        filename = safe_name

    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Cache-Control": "private, max-age=60",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
