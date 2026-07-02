import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import uuid
import logging
import os
import analytiq_data as ad
from typing import AsyncIterator, List, Literal, Optional, Union

import stamina
from botocore.exceptions import ClientError

from textractor.entities.document import Document

from analytiq_data.system import settings as system_settings

logger = logging.getLogger(__name__)

TextractPriority = Literal["high", "low"]


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


OCR_TIMEOUT_SECS = _get_int_env("OCR_TIMEOUT_SECS", 600)  # 10 min
# Per worker pod: max in-flight Textract jobs come from system_settings (refreshed every 25 gate acquisitions).
# ``TEXTRACT_MAX_CONCURRENT`` env seeds the default when no system_settings doc exists.

_textract_in_flight = 0
_textract_high_waiting = 0
_textract_gate: asyncio.Condition | None = None


def _get_textract_gate() -> asyncio.Condition:
    global _textract_gate
    if _textract_gate is None:
        _textract_gate = asyncio.Condition()
    return _textract_gate


@asynccontextmanager
async def _textract_concurrency(priority: TextractPriority = "high") -> AsyncIterator[None]:
    """Acquire a Textract slot; low priority yields while high-priority callers wait.

    Priority is best-effort (not strict FIFO): a low caller may occasionally acquire
    between two high callers. The slot covers the full job (S3 upload through polling).
    """
    global _textract_in_flight, _textract_high_waiting
    max_concurrent = await system_settings.get_textract_max_concurrent()
    if max_concurrent <= 0:
        yield
        return

    gate = _get_textract_gate()
    async with gate:
        if priority == "high":
            _textract_high_waiting += 1
            try:
                while _textract_in_flight >= max_concurrent:
                    await gate.wait()
                _textract_in_flight += 1
            finally:
                _textract_high_waiting -= 1
                gate.notify_all()
        else:
            while (
                _textract_in_flight >= max_concurrent
                or _textract_high_waiting > 0
            ):
                await gate.wait()
            _textract_in_flight += 1

    try:
        yield
    finally:
        async with gate:
            _textract_in_flight -= 1
            gate.notify_all()


def _aws_error_code(exc: BaseException) -> str | None:
    if not isinstance(exc, ClientError):
        return None
    try:
        err = exc.response.get("Error") or {}
        code = err.get("Code")
        return str(code) if code is not None else None
    except Exception:
        return None


def _is_textract_provisioned_throughput_exceeded(exc: BaseException) -> bool:
    """
    Textract (via botocore) raises ClientError with response Error.Code.
    We only retry the specific throughput error requested.
    """
    return _aws_error_code(exc) == "ProvisionedThroughputExceededException"


@stamina.retry(
    on=_is_textract_provisioned_throughput_exceeded,
    attempts=5,
    wait_initial=1.0,
    wait_max=20.0,
    timeout=120.0,
)
async def _call_textract_with_retry(fn, **kwargs):
    return await fn(**kwargs)


def _safe_block_page_int(block: object) -> Optional[int]:
    """Textract ``Page`` is typically int; tolerate missing or non-castable values."""
    if not isinstance(block, dict):
        return None
    p = block.get("Page")
    if p is None:
        return None
    try:
        return int(p)
    except (TypeError, ValueError):
        return None


def ocr_result_blocks(ocr_json: Union[list, dict]) -> List[dict]:
    """
    Normalize OCR payload from :func:`run_textract` or persisted :func:`analytiq_data.ocr.ocr.get_ocr_json`:
    either a legacy flat list of blocks or a dict shaped like ``GetDocumentAnalysis`` / ``GetDocumentTextDetection``.
    """
    if isinstance(ocr_json, dict) and "Blocks" in ocr_json:
        return ocr_json["Blocks"]
    return ocr_json


def configure_textractor_logging(level: int = logging.WARNING) -> None:
    """
    Raise the effective level for noisy textractor loggers (default: hide their INFO).

    - ``textractor.parsers.response_parser``: Textract often returns ``KEY_VALUE_SET``
      blocks whose relationships omit CHILD; textractor then emits one INFO line per block.
    - ``textractor.entities.table``: INFO when column-header heuristics skip using the first
      row as DataFrame columns (the message can show matching counts, e.g. "9 vs 9", when the
      real reason is the header-fraction threshold).

    Call before ``Document.open`` / page linearization when root logging is INFO and these
    lines are unwanted.
    """
    logging.getLogger("textractor.parsers.response_parser").setLevel(level)
    logging.getLogger("textractor.entities.table").setLevel(level)


def open_textract_document_from_ocr_json(
    ocr_json: Union[list, dict],
    *,
    document_id: str = "",
    org_id: Optional[str] = None,
) -> Document:
    """
    Parse stored OCR JSON into a textractor ``Document`` for linearization or export.

    Uses :func:`configure_textractor_logging` and :func:`textract_payload_for_document_open`.
    May mutate ``ocr_json`` in place (see ``textract_payload_for_document_open``).
    """
    configure_textractor_logging()
    payload = textract_payload_for_document_open(ocr_json)
    if payload is None:
        raise ValueError(
            f"{org_id}/{document_id}: unsupported OCR payload for textractor"
        )
    try:
        doc = Document.open(payload)
    except Exception as e:
        raise RuntimeError(
            f"{org_id}/{document_id}: Textractor Document.open failed: {e}"
        ) from e
    if not doc.pages:
        raise ValueError(
            f"{org_id}/{document_id}: no pages in textractor document"
        )
    return doc


async def run_textract(analytiq_client,
                       blob: bytes,
                       feature_types: list = [],
                       query_list: Optional[list] = None,
                       document_id: Optional[str] = None,
                       org_id: Optional[str] = None,
                       *,
                       priority: TextractPriority = "high") -> dict:
    """
    Run textract on a blob and return merged API-shaped results.

    Concurrency is limited per pod by ``system_settings.textract_max_concurrent``. Use ``priority="high"``
    for document OCR workers and the first item in a flow OCR batch; ``priority="low"`` for
    remaining flow batch items (best effort). One cached ``AsyncAWSClient`` per pod.

    Args:
        analytiq_client: Analytiq client
        doc_blob: Bytes to be textracted
        feature_types: List of feature types, e.g. ["LAYOUT", "TABLES", "FORMS", "SIGNATURES"]
        query_list: List of queries

    Returns:
        Dict with ``Blocks`` (merged across pagination), ``DocumentMetadata``, and model version fields
        from Textract (``AnalyzeDocumentModelVersion`` for analysis jobs,
        ``DetectDocumentTextModelVersion`` for text-detection-only jobs). Use :func:`ocr_result_blocks`
        if you only need the block list (also accepts legacy stored lists).
    """
    # Create a random s3 key
    s3_key = f"textract/tmp/{datetime.now().strftime('%Y-%m-%d')}/{uuid.uuid4()}"

    normalized_queries = None
    if query_list is not None and len(query_list) > 0:
        normalized_queries = [{"Text": str(q)} for q in query_list]

    loop = asyncio.get_running_loop()
    run_started_at = loop.time()

    if org_id and document_id:
        log_prefix = f"{org_id}/{document_id}"
    elif document_id:
        log_prefix = document_id
    else:
        log_prefix = ""

    async with _textract_concurrency(priority):
        aws_client = await ad.aws.get_aws_client_async(analytiq_client)
        s3_bucket_name = aws_client.s3_bucket_name
        try:
            for attempt in range(2):
                try:
                    # Pull fresh STS tokens from DeferredRefreshableCredentials before opening clients.
                    await aws_client.refresh_credentials()
                    prefix_part = f"{log_prefix}: " if log_prefix else ""
                    # Open S3 first; defer Textract until after upload (one fewer TLS handshake pre-upload).
                    async with aws_client.client("s3") as s3_client:
                        upload_started_at = loop.time()
                        logger.info(
                            f"{analytiq_client.name}: {prefix_part}uploading to S3 "
                            f"(blob_bytes={len(blob)}, s3://{s3_bucket_name}/{s3_key})"
                        )
                        await s3_client.put_object(
                            Bucket=s3_bucket_name, Key=s3_key, Body=blob
                        )
                        upload_secs = loop.time() - upload_started_at
                        logger.info(
                            f"{analytiq_client.name}: {prefix_part}uploaded to S3 "
                            f"(s3://{s3_bucket_name}/{s3_key}, upload_secs={upload_secs:.2f})"
                        )
                        try:
                            async with aws_client.client("textract") as textract_client:
                                if normalized_queries is not None:
                                    operation = "start_document_analysis"
                                elif len(feature_types) > 0:
                                    operation = "start_document_analysis"
                                else:
                                    operation = "start_document_text_detection"

                                prep_secs = loop.time() - run_started_at
                                logger.info(
                                    f"{analytiq_client.name}: {prefix_part}invoking Textract "
                                    f"{operation} (blob_bytes={len(blob)}, "
                                    f"s3://{s3_bucket_name}/{s3_key}, priority={priority}, "
                                    f"prep_secs={prep_secs:.2f})"
                                )

                                if normalized_queries is not None:
                                    response = await _call_textract_with_retry(
                                        textract_client.start_document_analysis,
                                        DocumentLocation={
                                            "S3Object": {
                                                "Bucket": s3_bucket_name,
                                                "Name": s3_key,
                                            }
                                        },
                                        FeatureTypes=feature_types + ["QUERIES"],
                                        QueriesConfig={"Queries": normalized_queries},
                                    )
                                    get_completion_func = textract_client.get_document_analysis
                                elif len(feature_types) > 0:
                                    response = await _call_textract_with_retry(
                                        textract_client.start_document_analysis,
                                        DocumentLocation={
                                            "S3Object": {
                                                "Bucket": s3_bucket_name,
                                                "Name": s3_key,
                                            }
                                        },
                                        FeatureTypes=feature_types,
                                    )
                                    get_completion_func = textract_client.get_document_analysis
                                else:
                                    response = await _call_textract_with_retry(
                                        textract_client.start_document_text_detection,
                                        DocumentLocation={
                                            "S3Object": {
                                                "Bucket": s3_bucket_name,
                                                "Name": s3_key,
                                            }
                                        },
                                    )
                                    get_completion_func = textract_client.get_document_text_detection

                                job_id = response["JobId"]

                                idx = 0
                                start_time = loop.time()
                                while True:
                                    elapsed = loop.time() - start_time
                                    if elapsed > OCR_TIMEOUT_SECS:
                                        raise asyncio.TimeoutError(
                                            f"Textract job {job_id} timed out after {OCR_TIMEOUT_SECS}s"
                                        )

                                    status_response = await _call_textract_with_retry(
                                        get_completion_func, JobId=job_id
                                    )
                                    status = status_response["JobStatus"]
                                    logger.info(
                                        f"{analytiq_client.name}: {prefix_part}step {idx}: {status}"
                                    )
                                    idx += 1

                                    if status in ["SUCCEEDED", "FAILED"]:
                                        break

                                    sleep_time = min(2 ** min(idx // 5, 3), 10)
                                    await asyncio.sleep(sleep_time)

                                idx = 0
                                if status == "SUCCEEDED":
                                    blocks = []
                                    document_metadata: Optional[dict] = None
                                    analyze_document_model_version: Optional[str] = None
                                    detect_document_text_model_version: Optional[str] = None
                                    first_result_page = True

                                    next_token = None
                                    while True:
                                        if next_token:
                                            response = await _call_textract_with_retry(
                                                get_completion_func,
                                                JobId=job_id,
                                                NextToken=next_token,
                                            )
                                        else:
                                            response = await _call_textract_with_retry(
                                                get_completion_func, JobId=job_id
                                            )

                                        if first_result_page:
                                            document_metadata = response.get("DocumentMetadata")
                                            analyze_document_model_version = response.get(
                                                "AnalyzeDocumentModelVersion"
                                            )
                                            detect_document_text_model_version = response.get(
                                                "DetectDocumentTextModelVersion"
                                            )
                                            first_result_page = False

                                        blocks.extend(response["Blocks"])
                                        next_token = response.get("NextToken", None)

                                        logger.info(
                                            f"{analytiq_client.name}: {prefix_part}step {idx}: "
                                            f"blocks len: {len(blocks)} next_token: {next_token}"
                                        )
                                        idx += 1
                                        if not next_token:
                                            break

                                    if not document_metadata:
                                        page_blocks = [
                                            b for b in blocks if b.get("BlockType") == "PAGE"
                                        ]
                                        document_metadata = {
                                            "Pages": len(page_blocks) if page_blocks else 1,
                                        }

                                    return {
                                        "Blocks": blocks,
                                        "DocumentMetadata": document_metadata,
                                        "AnalyzeDocumentModelVersion": analyze_document_model_version,
                                        "DetectDocumentTextModelVersion": detect_document_text_model_version,
                                    }

                                raise Exception(
                                    f"Textract document analysis failed: {status} "
                                    f"for s3://{s3_bucket_name}/{s3_key}"
                                )
                        finally:
                            try:
                                await s3_client.delete_object(
                                    Bucket=s3_bucket_name, Key=s3_key
                                )
                            except Exception as cleanup_error:
                                logger.warning(
                                    f"Failed to cleanup S3 object {s3_key}: {cleanup_error}"
                                )
                except Exception as e:
                    if attempt == 0 and aws_client.is_refreshable_auth_error(e):
                        logger.warning(
                            "AWS credentials expired during textract, refreshing and retrying"
                        )
                        continue
                    raise
        except Exception as e:
            logger.error(f"Error running textract: {e}")
            raise

def get_page_text_map(block_map: dict) -> dict:
    """
    Get the page text map keyed by **0-based** page index (AWS ``Page`` on blocks is 1-based).
    """
    page_text_map = {}
    for _, block in block_map.items():
        if block['BlockType'] == 'LINE':
            idx = int(block['Page']) - 1
            if idx not in page_text_map:
                page_text_map[idx] = ""
            page_text_map[idx] += block['Text'] + "\n"

    if len(page_text_map) == 0:
        return page_text_map

    max_idx = max(page_text_map.keys())
    for idx in range(0, max_idx + 1):
        page_text_map.setdefault(idx, "")

    return dict(sorted(page_text_map.items()))


def textract_payload_for_document_open(ocr_json: Union[list, dict]) -> Optional[dict]:
    """
    Build the API-shaped dict passed to ``textractor.entities.document.Document.open``.

    Returns ``None`` if ``ocr_json`` cannot be wrapped (caller should use LINE-based text).

    **Mutates** list/dict contents in place when passed to ``Document.open``: the ``textractor``
    response converter may rewrite block types and elide some layout blocks.
    """
    if isinstance(ocr_json, dict) and "Blocks" in ocr_json:
        return ocr_json
    if isinstance(ocr_json, list):
        blocks = ocr_json
        n = sum(1 for b in blocks if b.get("BlockType") == "PAGE")
        if not n:
            pnums = set()
            for b in blocks:
                pn = _safe_block_page_int(b)
                if pn is not None:
                    pnums.add(pn)
            n = max(pnums) if pnums else 1
        return {"Blocks": blocks, "DocumentMetadata": {"Pages": n}}
    return None


def page_text_map_from_ocr_document(doc) -> dict:
    """
    Map **0-based** page index to plain text from a **textractor** ``Document`` (``Page.get_text``
    linearization). Textractor uses 1-based ``page_num``; keys here are ``page_num - 1``.

    When no page has a valid ``page_num`` (e.g. some image-only scans) but ``doc.pages`` is
    non-empty, falls back to one entry per page in order, using each page's text (often empty).
    """
    if not doc.pages:
        return {}

    ordered = sorted(doc.pages, key=lambda p: (p.page_num, p.id))
    page_text_map = {}
    for p in ordered:
        if getattr(p, "page_num", None) and p.page_num > 0:
            idx = int(p.page_num) - 1
            page_text_map[idx] = p.text
    if not page_text_map:
        for i, p in enumerate(ordered):
            page_text_map[i] = getattr(p, "text", None) or ""
    max_idx = max(page_text_map.keys())
    for idx in range(0, max_idx + 1):
        page_text_map.setdefault(idx, "")
    return dict(sorted(page_text_map.items()))