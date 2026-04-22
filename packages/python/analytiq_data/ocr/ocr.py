from datetime import datetime, UTC
import asyncio
import json
import os
import pickle
import logging
import re
import tempfile
from typing import Any, Literal, Optional

import analytiq_data as ad

logger = logging.getLogger(__name__)

OCR_BUCKET = "ocr"


def markdown_to_plain_text(md: str) -> str:
    """Strip markdown to plain text for ``get_ocr_text`` / stored ``_text`` blobs."""
    if not md:
        return ""
    try:
        from markdown_it import MarkdownIt

        html = MarkdownIt().enable("table").render(md)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception as e:
        logger.warning(f"markdown_to_plain_text fallback: {e}")
        return re.sub(r"[#*_`\[\]()]", "", md)


def is_pages_markdown_ocr(obj: Any) -> bool:
    """True if payload is Mistral OCR or LLM OCR ``pages[].markdown`` shape."""
    if not isinstance(obj, dict):
        return False
    pages = obj.get("pages")
    if not isinstance(pages, list) or not pages:
        return False
    first = pages[0]
    return isinstance(first, dict) and "markdown" in first


def infer_ocr_type(ocr_json: Any) -> Literal["textract", "mistral", "mistral_vertex", "llm", "pymupdf"]:
    """Infer engine from stored JSON when GridFS metadata is missing."""
    if isinstance(ocr_json, dict) and ocr_json.get("ocr_engine") == "pymupdf":
        return "pymupdf"
    if is_pages_markdown_ocr(ocr_json):
        if isinstance(ocr_json, dict) and ocr_json.get("provider") is not None:
            return "llm"
        return "mistral"
    return "textract"


def decode_ocr_blob_bytes(blob_bytes: bytes) -> Any:
    """Load OCR JSON: UTF-8 JSON first, else legacy pickle."""
    if not blob_bytes:
        raise ValueError("empty OCR blob")
    stripped = blob_bytes.lstrip()
    if stripped[:1] in (b"{", b"["):
        try:
            return json.loads(blob_bytes.decode("utf-8"))
        except json.JSONDecodeError:
            pass
    return pickle.loads(blob_bytes)


async def get_ocr_json(
    analytiq_client, document_id: str
) -> list | dict | None:
    """Get OCR data: legacy flat list, Textract dict, or JSON (Mistral/LLM pages)."""
    key = f"{document_id}_json"
    ocr_blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)

    if ocr_blob is None:
        key = f"{document_id}_list"
        ocr_blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)

    if ocr_blob is None:
        return None

    blob_bytes = ocr_blob["blob"]
    return await asyncio.to_thread(decode_ocr_blob_bytes, blob_bytes)


async def save_ocr_json(
    analytiq_client,
    document_id: str,
    ocr_json,
    metadata: dict = None,
    *,
    encoding: Literal["json", "pickle"] = "json",
):
    """
    Save OCR payload to GridFS.

    New writes use UTF-8 JSON with ``metadata["ocr_type"]`` in
    {``textract``, ``mistral``, ``llm``, ``pymupdf``}. Legacy callers may use ``pickle``.
    """
    key = f"{document_id}_json"
    if metadata is None:
        metadata = {}
    if encoding == "json":
        if "ocr_type" not in metadata:
            logger.warning(
                f"save_ocr_json missing ocr_type in metadata for document_id={document_id}"
            )
        body = await asyncio.to_thread(
            lambda: json.dumps(ocr_json, ensure_ascii=False, default=str).encode("utf-8")
        )
    else:
        body = await asyncio.to_thread(pickle.dumps, ocr_json)
    size_mb = len(body) / 1024 / 1024
    logger.info(
        f"Saving OCR json for {document_id} with metadata: {metadata} "
        f"size: {size_mb:.2f}MB encoding={encoding}"
    )
    await ad.mongodb.save_blob_async(
        analytiq_client, bucket=OCR_BUCKET, key=key, blob=body, metadata=metadata
    )
    logger.info(f"OCR JSON for {document_id} has been saved.")


async def delete_ocr_json(analytiq_client, document_id: str):
    key = f"{document_id}_json"
    await ad.mongodb.delete_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)
    logger.debug(f"OCR JSON for {document_id} has been deleted.")


async def get_ocr_text(analytiq_client, document_id: str, page_idx: int = None) -> str:
    key = f"{document_id}_text"
    if page_idx is not None:
        key += f"_page_{page_idx}"
    blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)
    if blob is None:
        return None
    return blob["blob"].decode("utf-8")


async def save_ocr_text(
    analytiq_client,
    document_id: str,
    ocr_text: str,
    page_idx: int = None,
    metadata: dict = None,
):
    key = f"{document_id}_text"
    if page_idx is not None:
        key += f"_page_{page_idx}"
    ocr_text_bytes = ocr_text.encode("utf-8")
    await ad.mongodb.save_blob_async(
        analytiq_client, bucket=OCR_BUCKET, key=key, blob=ocr_text_bytes, metadata=metadata
    )
    logger.debug(f"OCR text for {document_id} page {page_idx} has been saved.")


async def delete_ocr_text(analytiq_client, document_id: str, page_idx: int = None):
    key = f"{document_id}_text"
    if page_idx is not None:
        key += f"_page_{page_idx}"
    await ad.mongodb.delete_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)
    logger.debug(f"OCR text for {document_id} page {page_idx} has been deleted.")


async def delete_ocr_all(analytiq_client, document_id: str):
    n_pages = await get_ocr_n_pages(analytiq_client, document_id)
    for page_idx in range(n_pages):
        await delete_ocr_text(analytiq_client, document_id, page_idx)
    await delete_ocr_text(analytiq_client, document_id)
    await delete_ocr_json(analytiq_client, document_id)


def _page_text_map_from_pages_markdown(ocr_json: dict) -> dict[int, str]:
    pages = sorted(ocr_json.get("pages") or [], key=lambda p: p.get("index", 0))
    out: dict[int, str] = {}
    for p in pages:
        idx = int(p.get("index", 0))
        md = p.get("markdown") or ""
        out[idx] = markdown_to_plain_text(md)
    return out


async def save_ocr_text_from_json(
    analytiq_client,
    document_id: str,
    ocr_json,
    metadata: dict = None,
    force: bool = False,
    org_id: str = None,
    ocr_type: Optional[Literal["textract", "mistral", "llm", "pymupdf"]] = None,
):
    """
    Build and save per-page and full-document plain text from stored OCR JSON.

    ``ocr_type`` selects Textract vs pages-markdown (Mistral / LLM / PyMuPDF). If omitted, inferred.
    """
    ot = ocr_type or infer_ocr_type(ocr_json)

    if ot in ("mistral", "mistral_vertex", "llm", "pymupdf"):
        if not isinstance(ocr_json, dict) or not is_pages_markdown_ocr(ocr_json):
            raise ValueError(
                f"{org_id}/{document_id}: expected pages[].markdown OCR payload for ocr_type={ot}"
            )
        page_text_map = _page_text_map_from_pages_markdown(ocr_json)
    else:
        def _parse_textract():
            doc = ad.aws.textract.open_textract_document_from_ocr_json(
                ocr_json, document_id=document_id, org_id=org_id
            )
            return ad.aws.textract.page_text_map_from_ocr_document(doc)

        page_text_map = await asyncio.to_thread(_parse_textract)

    if not force:
        ocr_text = await get_ocr_text(analytiq_client, document_id)
        if ocr_text is not None:
            logger.info(f"{org_id}/{document_id} OCR text already exists, returning")
            return
    else:
        old_n = await get_ocr_n_pages(analytiq_client, document_id)
        await delete_ocr_text(analytiq_client, document_id)
        n_new = max(page_text_map.keys()) + 1 if page_text_map else 0
        for page_idx in range(max(n_new, old_n)):
            await delete_ocr_text(analytiq_client, document_id, page_idx)

    if metadata is None:
        metadata = {}
    metadata["n_pages"] = len(page_text_map)
    metadata["ocr_type"] = ot

    for page_idx, page_text in sorted(page_text_map.items()):
        await save_ocr_text(analytiq_client, document_id, page_text, page_idx, metadata)
        logger.info(f"{org_id}/{document_id}: OCR text saved for page page_idx={page_idx}")

    text = "\n".join(page_text_map[k] for k in sorted(page_text_map))
    logger.info(
        f"{org_id}/{document_id}: Saving full OCR text metadata={metadata} length={len(text)}"
    )
    await save_ocr_text(analytiq_client, document_id, text, metadata=metadata)
    logger.info(f"{org_id}/{document_id}: OCR text save complete")


async def get_ocr_metadata(analytiq_client, document_id: str) -> dict:
    blob = await ad.mongodb.get_blob_async(
        analytiq_client, bucket=OCR_BUCKET, key=f"{document_id}_text"
    )
    if blob is None:
        return None
    return {
        "n_pages": blob["metadata"].get("n_pages", 0),
        "ocr_date": blob.get("upload_date", None),
        "ocr_type": blob["metadata"].get("ocr_type", None),
    }


async def get_ocr_n_pages(analytiq_client, document_id: str) -> int:
    key = f"{document_id}_text"
    blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)
    if blob is None:
        return 0
    if blob.get("metadata") is None:
        return 0
    return blob["metadata"].get("n_pages", 0)


def export_pages_markdown_full_text(ocr_json: dict) -> str:
    """Join ``pages[].markdown`` for Mistral / LLM OCR payloads (index order)."""
    pages = sorted(ocr_json.get("pages") or [], key=lambda p: p.get("index", 0))
    parts = [p.get("markdown") or "" for p in pages]
    return "\n\n".join(parts)


def _export_ocr_markdown_sync(ocr_json, *, document_id: str, org_id: Optional[str]) -> str:
    if is_pages_markdown_ocr(ocr_json):
        return export_pages_markdown_full_text(ocr_json)
    doc = ad.aws.textract.open_textract_document_from_ocr_json(
        ocr_json, document_id=document_id, org_id=org_id
    )
    return doc.to_markdown()


def _export_ocr_html_sync(ocr_json, *, document_id: str, org_id: Optional[str]) -> str:
    if is_pages_markdown_ocr(ocr_json):
        from markdown_it import MarkdownIt

        md = MarkdownIt().enable("table")
        parts = []
        for p in sorted(ocr_json.get("pages") or [], key=lambda x: x.get("index", 0)):
            parts.append(md.render(p.get("markdown") or ""))
        return "\n".join(parts)
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
    if is_pages_markdown_ocr(ocr_json):
        raise ValueError(
            f"{org_id}/{document_id}: Excel table export requires Textract OCR, not pages-markdown"
        )
    doc = ad.aws.textract.open_textract_document_from_ocr_json(
        ocr_json, document_id=document_id, org_id=org_id
    )
    if not doc.tables:
        raise ValueError(f"{org_id}/{document_id}: no tables in OCR for Excel export")
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
    """Linearize OCR to Markdown from stored OCR JSON."""
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
    """Linearize OCR to HTML from stored OCR JSON."""
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
