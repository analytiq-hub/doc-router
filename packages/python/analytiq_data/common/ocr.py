from datetime import datetime, UTC
import asyncio
import os
import pickle
import logging
import tempfile
from typing import Optional

import analytiq_data as ad

logger = logging.getLogger(__name__)

OCR_BUCKET = "ocr"

async def get_ocr_json(analytiq_client, document_id: str) -> list:
    """Get OCR data: legacy flat list of blocks or dict with ``Blocks`` and Textract metadata."""
    # Try new format first
    key = f"{document_id}_json"
    ocr_blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)
    
    # Fall back to old format if not found
    if ocr_blob is None:
        key = f"{document_id}_list"
        ocr_blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)
        
    if ocr_blob is None:
        return None
        
    return pickle.loads(ocr_blob["blob"])
   

async def save_ocr_json(analytiq_client, document_id:str, ocr_json, metadata:dict=None):
    """Save OCR JSON (flat block list or full Textract-shaped dict from :func:`run_textract`)."""
    key = f"{document_id}_json"
    ocr_bytes = pickle.dumps(ocr_json)
    size_mb = len(ocr_bytes) / 1024 / 1024
    logger.info(f"Saving OCR json for {document_id} with metadata: {metadata} size: {size_mb:.2f}MB")
    await ad.mongodb.save_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key, blob=ocr_bytes, metadata=metadata)
    
    logger.info(f"OCR JSON for {document_id} has been saved.")

async def delete_ocr_json(analytiq_client, document_id:str):
    """
    Delete the OCR JSON

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id
    """
    key = f"{document_id}_json"
    await ad.mongodb.delete_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)

    logger.debug(f"OCR JSON for {document_id} has been deleted.")

async def get_ocr_text(analytiq_client, document_id:str, page_idx:int=None) -> str:
    """
    Get the OCR text
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id
        page_idx : int
            page index. If None, return the whole OCR text.

    Returns:
        str
            OCR text
    """
    key = f"{document_id}_text"
    if page_idx is not None:
        key += f"_page_{page_idx}"
    blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)
    if blob is None:
        return None
    return blob["blob"].decode("utf-8")
   

async def save_ocr_text(analytiq_client, document_id:str, ocr_text:str, page_idx:int=None, metadata:dict=None):
    """
    Save the OCR text
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id
        ocr_text : str
            OCR text
        page_idx : int
            page index
        metadata : dict
            OCR metadata
    """
    key = f"{document_id}_text"
    if page_idx is not None:
        key += f"_page_{page_idx}"
    
    # Convert the text to bytes 
    ocr_text_bytes = ocr_text.encode("utf-8")

    # Save the blob
    await ad.mongodb.save_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key, blob=ocr_text_bytes, metadata=metadata)
    
    logger.debug(f"OCR text for {document_id} page {page_idx} has been saved.")

async def delete_ocr_text(analytiq_client, document_id:str, page_idx:int=None):
    """
    Delete the OCR text

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id
        page_idx : int
            page index
    """
    key = f"{document_id}_text"
    if page_idx is not None:
        key += f"_page_{page_idx}"
    await ad.mongodb.delete_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)

    logger.debug(f"OCR text for {document_id} page {page_idx} has been deleted.")

async def delete_ocr_all(analytiq_client, document_id:str):
    """
    Delete the OCR

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id
    """
    n_pages = await get_ocr_n_pages(analytiq_client, document_id)
    for page_idx in range(n_pages):
        await delete_ocr_text(analytiq_client, document_id, page_idx)
    await delete_ocr_text(analytiq_client, document_id)
    await delete_ocr_json(analytiq_client, document_id)

async def save_ocr_text_from_json(
    analytiq_client,
    document_id: str,
    ocr_json,
    metadata: dict = None,
    force: bool = False,
    org_id: str = None,
):
    """
    Save the OCR text from the OCR list
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id
        ocr_json : list or dict
            Flat block list or dict with ``Blocks`` (from :func:`run_textract`)
        metadata : dict
            OCR metadata
        force : bool
            Whether to force the processing
        org_id : str, optional
            Organization id for error messages (recommended when known)
    """
    doc = ad.aws.textract.open_textract_document_from_ocr_json(
        ocr_json, document_id=document_id, org_id=org_id
    )

    page_text_map = ad.aws.textract.page_text_map_from_ocr_document(doc)
    if not page_text_map:
        raise ValueError(
            f"{org_id}/{document_id}: no page text from textractor document"
        )

    if not force:
        ocr_text = await get_ocr_text(analytiq_client, document_id)
        if ocr_text is not None:
            logger.info(
                f"{org_id}/{document_id} OCR text already exists, returning"
            )
            return
    else:
        # Remove the old OCR text, if any
        await delete_ocr_text(analytiq_client, document_id)
        for page_idx in range(len(page_text_map)):
            await delete_ocr_text(analytiq_client, document_id, page_idx)
    
    # Record the number of pages in the metadata
    if metadata is None:
        metadata = {}
    metadata["n_pages"] = len(page_text_map)
    
    # Save the new OCR text (page_text_map keys are 0-based page indices)
    for page_idx, page_text in sorted(page_text_map.items()):
        await save_ocr_text(analytiq_client, document_id, page_text, page_idx, metadata)
        logger.info(
            f"{org_id}/{document_id}: OCR text saved for page page_idx={page_idx}"
        )

    text = "\n".join(page_text_map[k] for k in sorted(page_text_map))
    logger.info(
        f"{org_id}/{document_id}: Saving full OCR text metadata={metadata} length={len(text)}"
    )
    await save_ocr_text(analytiq_client, document_id, text, metadata=metadata)

    logger.info(f"{org_id}/{document_id}: OCR text save complete")

async def get_ocr_metadata(analytiq_client, document_id:str) -> dict:
    """
    Get the OCR metadata
    """
    blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=f"{document_id}_text")
    if blob is None:
        return None

    metadata = {
        "n_pages": blob["metadata"].get("n_pages", 0),
        "ocr_date": blob.get("upload_date", None)
    }
    return metadata

async def get_ocr_n_pages(analytiq_client, document_id:str) -> int:
    """
    Get the number of pages in the OCR text

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id

    Returns:
        int
            Number of pages in the OCR text
    """
    key = f"{document_id}_text"
    blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)
    if blob is None:
        return 0
    if blob.get("metadata") is None:
        return 0
    return blob["metadata"].get("n_pages", 0)


def _export_ocr_markdown_sync(ocr_json, *, document_id: str, org_id: Optional[str]) -> str:
    doc = ad.aws.textract.open_textract_document_from_ocr_json(
        ocr_json, document_id=document_id, org_id=org_id
    )
    return doc.to_markdown()


def _export_ocr_html_sync(ocr_json, *, document_id: str, org_id: Optional[str]) -> str:
    doc = ad.aws.textract.open_textract_document_from_ocr_json(
        ocr_json, document_id=document_id, org_id=org_id
    )
    return doc.to_html()


def _export_ocr_tables_excel_sync(
    ocr_json,
    *,
    document_id: str,
    org_id: Optional[str],
    table_index: Optional[int],
) -> bytes:
    doc = ad.aws.textract.open_textract_document_from_ocr_json(
        ocr_json, document_id=document_id, org_id=org_id
    )
    if not doc.tables:
        raise ValueError(
            f"{org_id}/{document_id}: no tables in OCR for Excel export"
        )
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        if table_index is not None:
            if table_index < 0 or table_index >= len(doc.tables):
                raise ValueError(
                    f"{org_id}/{document_id}: table_index out of range "
                    f"(have {len(doc.tables)} tables)"
                )
            doc.tables[table_index].to_excel(filepath=path)
        else:
            doc.export_tables_to_excel(path)
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


async def export_ocr_markdown(
    analytiq_client,
    document_id: str,
    *,
    org_id: Optional[str] = None,
) -> str:
    """Linearize OCR to Markdown via textractor (on the fly from stored OCR JSON)."""
    ocr_json = await get_ocr_json(analytiq_client, document_id)
    if ocr_json is None:
        raise ValueError(f"{org_id}/{document_id}: OCR data not found")
    return await asyncio.to_thread(
        _export_ocr_markdown_sync,
        ocr_json,
        document_id=document_id,
        org_id=org_id,
    )


async def export_ocr_html(
    analytiq_client,
    document_id: str,
    *,
    org_id: Optional[str] = None,
) -> str:
    """Linearize OCR to HTML via textractor (on the fly from stored OCR JSON)."""
    ocr_json = await get_ocr_json(analytiq_client, document_id)
    if ocr_json is None:
        raise ValueError(f"{org_id}/{document_id}: OCR data not found")
    return await asyncio.to_thread(
        _export_ocr_html_sync,
        ocr_json,
        document_id=document_id,
        org_id=org_id,
    )


async def export_ocr_tables_excel(
    analytiq_client,
    document_id: str,
    *,
    org_id: Optional[str] = None,
    table_index: Optional[int] = None,
) -> bytes:
    """
    Export table(s) to ``.xlsx`` via textractor (on the fly from stored OCR JSON).

    If ``table_index`` is ``None``, all tables share one workbook (one sheet per table).
    If set, export that single table (0-based index).
    """
    ocr_json = await get_ocr_json(analytiq_client, document_id)
    if ocr_json is None:
        raise ValueError(f"{org_id}/{document_id}: OCR data not found")
    return await asyncio.to_thread(
        _export_ocr_tables_excel_sync,
        ocr_json,
        document_id=document_id,
        org_id=org_id,
        table_index=table_index,
    )
