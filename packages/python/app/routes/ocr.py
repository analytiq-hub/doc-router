# ocr.py

# Standard library imports
import asyncio
import gzip
import json
import logging
from typing import Literal, Optional
from pydantic import BaseModel

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse

# Local imports
import analytiq_data as ad
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

    document = await ad.common.get_doc(analytiq_client, document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_name = document.get("user_file_name", "")
    if not ad.common.doc.ocr_supported(file_name):
        raise HTTPException(status_code=404, detail="OCR not supported for this document extension")

    # Get the OCR JSON data from mongodb
    ocr_json = await ad.common.get_ocr_json(analytiq_client, document_id)
    if ocr_json is None:
        raise HTTPException(status_code=404, detail="OCR data not found")

    headers = {"Cache-Control": "private, max-age=3600"}

    if format == "gzip":
        # Run CPU-bound json.dumps + gzip.compress in a thread pool so the event loop is not blocked
        def _serialize_and_compress(data: list) -> bytes:
            return gzip.compress(json.dumps(data).encode("utf-8"))

        body = await asyncio.to_thread(_serialize_and_compress, ocr_json)
        return Response(
            content=body,
            media_type="application/json",
            headers={**headers, "Content-Encoding": "gzip"},
        )

    return JSONResponse(content=ocr_json, headers=headers)

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
    document = await ad.common.get_doc(analytiq_client, document_id)
    
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
    text = await ad.common.get_ocr_text(analytiq_client, document_id, page_idx)
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
    document = await ad.common.get_doc(analytiq_client, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    file_name = document.get("user_file_name", "")
    if not ad.common.doc.ocr_supported(file_name):
        raise HTTPException(status_code=404, detail="OCR not supported for this document extension")

    # Get the OCR metadata from mongodb
    metadata = await ad.common.get_ocr_metadata(analytiq_client, document_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="OCR metadata not found")
    
    return GetOCRMetadataResponse(
        n_pages=metadata["n_pages"],
        ocr_date=metadata["ocr_date"].isoformat()
    )
