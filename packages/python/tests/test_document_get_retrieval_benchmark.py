"""
Benchmark upload and GET /v0/orgs/{org}/documents/{id}.

Three tests, all using synthetic PDF-shaped blobs (and optionally a real PDF):
  1. JSON upload (base64 body)  + JSON GET (base64 response)
  2. Multipart upload (raw bytes) + JSON GET (base64 response)
  3. Multipart upload (raw bytes) + binary GET (/file endpoint)

Run (benchmark results only, no log noise):
  pytest -s packages/python/tests/test_document_get_retrieval_benchmark.py

Modes (env vars):
  RUN_DOC_RETRIEVAL_BENCHMARK_LARGE=1          add 100 MiB size
  RUN_DOC_RETRIEVAL_BENCHMARK_PARALLEL=<N>     concurrent uploads+GETs per size (default 1)
  BENCHMARK_REAL_PDF_PATH=/path/to/file.pdf    use a real PDF (third test skips if missing)
"""

from __future__ import annotations

import base64
import logging
import os
import statistics
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers

_DEFAULT_REAL_PDF = Path(
    "/Users/andrei/Downloads/"
    "WAX_2026_02_13_8254081_10582781282_KLUTH_GEORGE H-1.PDF"
)


@pytest.fixture(autouse=True)
def _suppress_logs():
    """Silence application logs so only benchmark results appear with -s."""
    prev = logging.root.manager.disable
    logging.disable(logging.WARNING)
    yield
    logging.disable(prev)


def _real_pdf_path() -> Path:
    raw = os.environ.get("BENCHMARK_REAL_PDF_PATH", "").strip()
    return Path(raw) if raw else _DEFAULT_REAL_PDF


_PDF_PREFIX = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _synthetic_pdf_bytes(size_bytes: int) -> bytes:
    if size_bytes < len(_PDF_PREFIX):
        return _PDF_PREFIX[:size_bytes]
    return _PDF_PREFIX + b"\x00" * (size_bytes - len(_PDF_PREFIX))


def _benchmark_sizes() -> list[tuple[int, str]]:
    sizes: list[tuple[int, str]] = [
        (max(1, int(0.1 * 1024 * 1024)), "0.1MiB"),
        (1 * 1024 * 1024, "1MiB"),
        (10 * 1024 * 1024, "10MiB"),
    ]
    if os.environ.get("RUN_DOC_RETRIEVAL_BENCHMARK_LARGE", "").strip().lower() in ("1", "true", "yes"):
        sizes.append((100 * 1024 * 1024, "100MiB"))
    return sizes


def _parallel_count() -> int:
    try:
        return max(1, int(os.environ.get("RUN_DOC_RETRIEVAL_BENCHMARK_PARALLEL", "1").strip()))
    except ValueError:
        return 1


def _min_median_max(values: list[float]) -> tuple[float, float, float]:
    s = sorted(values)
    return s[0], statistics.median(s), s[-1]


def _per_request_mib_per_s(latencies_s: list[float], mib: float) -> list[float]:
    return [mib / max(t, 1e-18) for t in latencies_s]


def _fmt_mmm(a: float, b: float, c: float, *, d: int) -> str:
    return f"min={a:.{d}f} med={b:.{d}f} max={c:.{d}f}"


# UploadFn: (index, blob, label) -> (index, response, elapsed_s)
UploadFn = Callable[[int, bytes, str], tuple[int, Any, float]]
# GetFn: (index, doc_id) -> (index, response, elapsed_s)
GetFn = Callable[[tuple[int, str]], tuple[int, Any, float]]


def _run_benchmark(
    upload_fn: UploadFn,
    get_fn: GetFn,
    validate_get: Callable[[Any, int, int, str], None],
    capsys: Any,
    header: str,
    footer: str = "",
) -> None:
    rows: list[str] = []
    parallel = _parallel_count()

    for size_bytes, label in _benchmark_sizes():
        blob = _synthetic_pdf_bytes(size_bytes)

        t_up0 = time.perf_counter()
        if parallel == 1:
            _, up, lat0 = upload_fn(0, blob, label)
            upload_responses, upload_each_s = [up], [lat0]
        else:
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                parts = list(pool.map(lambda i: upload_fn(i, blob, label), range(parallel)))
            upload_responses = [r for _, r, _ in parts]
            upload_each_s = [dt for _, _, dt in parts]
        upload_s = time.perf_counter() - t_up0

        for idx, up in enumerate(upload_responses):
            assert up.status_code == 200, f"upload failed ({label}) #{idx}: {up.status_code} {up.text}"

        doc_ids = [_extract_doc_id(up) for up in upload_responses]

        t_get0 = time.perf_counter()
        if parallel == 1:
            _, resp, lat0 = get_fn((0, doc_ids[0]))
            get_responses, get_each_s = [resp], [lat0]
        else:
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                parts = list(pool.map(get_fn, enumerate(doc_ids)))
            get_responses = [r for _, r, _ in parts]
            get_each_s = [dt for _, _, dt in parts]
        get_s = time.perf_counter() - t_get0

        for idx, resp in enumerate(get_responses):
            assert resp.status_code == 200, f"get failed ({label}) #{idx}: {resp.status_code} {resp.text}"
            validate_get(resp, idx, size_bytes, label)

        mib = size_bytes / (1024 * 1024)
        total_mib = mib * parallel
        par_note = f" x{parallel}" if parallel != 1 else ""
        row = (
            f"{label:>8}{par_note}  upload={upload_s:8.3f}s ({total_mib/upload_s:6.2f} MiB/s agg)  "
            f"get={get_s:8.3f}s ({total_mib/get_s:6.2f} MiB/s agg)"
        )

        up_min, up_med, up_max = _min_median_max(upload_each_s)
        get_min, get_med, get_max = _min_median_max(get_each_s)
        up_bw = _per_request_mib_per_s(upload_each_s, mib)
        get_bw = _per_request_mib_per_s(get_each_s, mib)
        row += (
            f"\n      POST latency (s):  {_fmt_mmm(up_min, up_med, up_max, d=3)}"
            f"\n      POST MiB/s (file): {_fmt_mmm(*_min_median_max(up_bw), d=2)}"
            f"\n      GET latency (s):   {_fmt_mmm(get_min, get_med, get_max, d=3)}"
            f"\n      GET MiB/s (file):  {_fmt_mmm(*_min_median_max(get_bw), d=2)}"
        )
        if parallel > 1:
            row += (
                f"\n      POST each (s): [{' '.join(f'{x:.3f}' for x in upload_each_s)}]"
                f"\n      GET each (s):  [{' '.join(f'{x:.3f}' for x in get_each_s)}]"
            )
        rows.append(row)

    table = f"\n  {header}\n  " + "\n  ".join(rows) + "\n"
    if footer:
        table += f"  {footer}\n"
    table += (
        "  (100MiB: RUN_DOC_RETRIEVAL_BENCHMARK_LARGE=1)\n"
        "  (parallel: RUN_DOC_RETRIEVAL_BENCHMARK_PARALLEL=<N>)\n"
    )
    with capsys.disabled():
        print(table)


def _extract_doc_id(response: Any) -> str:
    body = response.json()
    if "document" in body:
        return body["document"]["document_id"]
    return body["documents"][0]["document_id"]


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------

def _upload_json(i: int, blob: bytes, label: str) -> tuple[int, Any, float]:
    b64 = base64.b64encode(blob).decode("ascii")
    fname = f"bench-{label}.pdf" if _parallel_count() == 1 else f"bench-{label}-{i}.pdf"
    t0 = time.perf_counter()
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json={"documents": [{"name": fname, "content": b64, "tag_ids": [], "metadata": {"benchmark": "json"}}]},
        headers=get_auth_headers(),
    )
    return i, r, time.perf_counter() - t0


def _upload_multipart(i: int, blob: bytes, label: str) -> tuple[int, Any, float]:
    fname = f"bench-{label}.pdf" if _parallel_count() == 1 else f"bench-{label}-{i}.pdf"
    t0 = time.perf_counter()
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents/multipart",
        files=[("file", (fname, blob, "application/pdf"))],
        data={"name": fname, "tag_ids": "[]", "metadata": '{"benchmark":"multipart"}'},
        headers={"Authorization": "Bearer test_token"},
    )
    return i, r, time.perf_counter() - t0


# ---------------------------------------------------------------------------
# GET helpers + validators
# ---------------------------------------------------------------------------

def _get_json(idx_doc: tuple[int, str]) -> tuple[int, Any, float]:
    idx, doc_id = idx_doc
    t0 = time.perf_counter()
    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
        params={"file_type": "pdf"},
        headers=get_auth_headers(),
    )
    return idx, r, time.perf_counter() - t0


def _get_file(idx_doc: tuple[int, str]) -> tuple[int, Any, float]:
    idx, doc_id = idx_doc
    t0 = time.perf_counter()
    r = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}/file",
        params={"file_type": "pdf"},
        headers=get_auth_headers(),
    )
    return idx, r, time.perf_counter() - t0


def _validate_json_get(resp: Any, idx: int, size_bytes: int, label: str) -> None:
    content_b64 = resp.json().get("content")
    assert content_b64 is not None
    got = base64.b64decode(content_b64)
    assert len(got) == size_bytes, f"size mismatch {label} #{idx}: expected {size_bytes}, got {len(got)}"


def _validate_binary_get(resp: Any, idx: int, size_bytes: int, label: str) -> None:
    assert len(resp.content) == size_bytes, f"size mismatch {label} #{idx}: expected {size_bytes}, got {len(resp.content)}"


# ---------------------------------------------------------------------------
# Benchmark tests
# ---------------------------------------------------------------------------

@pytest.mark.doc_retrieval_benchmark
def test_upload_json_get_json(mock_auth, test_db, capsys) -> None:
    """Upload: POST /documents (base64 JSON).  GET: /documents/{id}?file_type=pdf (base64 JSON)."""
    _run_benchmark(
        _upload_json, _get_json, _validate_json_get, capsys,
        header="upload=JSON/base64  get=JSON/base64",
    )


@pytest.mark.doc_retrieval_benchmark
def test_upload_multipart_get_json(mock_auth, test_db, capsys) -> None:
    """Upload: POST /documents/multipart (raw bytes).  GET: /documents/{id}?file_type=pdf (base64 JSON)."""
    _run_benchmark(
        _upload_multipart, _get_json, _validate_json_get, capsys,
        header="upload=multipart  get=JSON/base64",
    )


@pytest.mark.doc_retrieval_benchmark
def test_upload_multipart_get_file(mock_auth, test_db, capsys) -> None:
    """Upload: POST /documents/multipart (raw bytes).  GET: /documents/{id}/file (raw binary)."""
    _run_benchmark(
        _upload_multipart, _get_file, _validate_binary_get, capsys,
        header="upload=multipart  get=/file (binary)",
    )


@pytest.mark.doc_retrieval_benchmark
def test_get_document_pdf_roundtrip_real_file(mock_auth, test_db, capsys) -> None:
    """
    Upload a real PDF from disk via multipart, GET /file, assert byte-exact round-trip.
    Skips if the file does not exist. Override path with BENCHMARK_REAL_PDF_PATH.
    """
    pdf_path = _real_pdf_path()
    if not pdf_path.is_file():
        pytest.skip(f"Real PDF not found: {pdf_path} (set BENCHMARK_REAL_PDF_PATH)")

    raw = pdf_path.read_bytes()
    assert raw.startswith(b"%PDF"), f"Not a PDF: {pdf_path}"

    t_up0 = time.perf_counter()
    up = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents/multipart",
        files=[("file", (pdf_path.name, raw, "application/pdf"))],
        data={"name": pdf_path.name, "tag_ids": "[]", "metadata": "{}"},
        headers={"Authorization": "Bearer test_token"},
    )
    upload_s = time.perf_counter() - t_up0
    assert up.status_code == 200, f"upload failed: {up.status_code} {up.text}"
    doc_id = up.json()["document"]["document_id"]

    t_get0 = time.perf_counter()
    resp = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}/file",
        params={"file_type": "pdf"},
        headers=get_auth_headers(),
    )
    get_s = time.perf_counter() - t_get0

    assert resp.status_code == 200, f"get failed: {resp.status_code} {resp.text}"
    assert resp.content == raw, f"round-trip mismatch: expected {len(raw)} bytes, got {len(resp.content)}"

    mib = len(raw) / (1024 * 1024)
    with capsys.disabled():
        print(
            f"\n  real PDF {pdf_path.name!r} ({mib:.2f} MiB)"
            f"  upload={upload_s:.3f}s  get={get_s:.3f}s  doc_id={doc_id}\n"
        )
