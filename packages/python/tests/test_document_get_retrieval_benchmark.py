"""
Benchmark GET /v0/orgs/{org}/documents/{id}?file_type=pdf (full JSON + base64 body).

Uploads synthetic PDF-shaped blobs, then measures wall-clock time for one retrieval per size.

Default run: 0.1 MiB, 1 MiB, and 10 MiB (CI still exercises a large JSON+base64 upload).
100 MiB: set RUN_DOC_RETRIEVAL_BENCHMARK_LARGE=1 (high memory; ~133 MiB JSON for upload at 100 MiB).

Parallel uploads (and matching parallel GETs): RUN_DOC_RETRIEVAL_BENCHMARK_PARALLEL (default 1), e.g. 32.
The JSON benchmark uses POST /documents (base64). A second test uses POST /documents/multipart for the same
sizes and parallelism so you can compare aggregate and per-request timings side by side.

Show timings: pytest -s packages/python/tests/test_document_get_retrieval_benchmark.py

Real PDF round-trip (optional): place the file at the default path below or set BENCHMARK_REAL_PDF_PATH.
If the file is missing, the test is skipped (CI-friendly).
"""

from __future__ import annotations

import base64
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers

# Default: same document as file:///Users/andrei/Downloads/WAX_2026_02_13_8254081_10582781282_KLUTH_GEORGE%20H-1.PDF
_DEFAULT_REAL_PDF = Path(
    "/Users/andrei/Downloads/"
    "WAX_2026_02_13_8254081_10582781282_KLUTH_GEORGE H-1.PDF"
)


def _real_pdf_path() -> Path:
    raw = os.environ.get("BENCHMARK_REAL_PDF_PATH", "").strip()
    return Path(raw) if raw else _DEFAULT_REAL_PDF


# Minimal PDF header so uploads are treated as PDF; remainder is padding.
_PDF_PREFIX = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _synthetic_pdf_bytes(size_bytes: int) -> bytes:
    if size_bytes < len(_PDF_PREFIX):
        return _PDF_PREFIX[:size_bytes]
    return _PDF_PREFIX + b"\x00" * (size_bytes - len(_PDF_PREFIX))


def _benchmark_sizes():
    """(size_bytes, label) in order."""
    sizes: list[tuple[int, str]] = [
        (max(1, int(0.1 * 1024 * 1024)), "0.1MiB"),
        (1 * 1024 * 1024, "1MiB"),
        (10 * 1024 * 1024, "10MiB"),
    ]
    env = os.environ.get("RUN_DOC_RETRIEVAL_BENCHMARK_LARGE", "").strip().lower()
    if env in ("1", "true", "yes", "all"):
        sizes.append((100 * 1024 * 1024, "100MiB"))
    return sizes


def _parallel_count() -> int:
    """Concurrent upload/GET requests per size (default 1)."""
    raw = os.environ.get("RUN_DOC_RETRIEVAL_BENCHMARK_PARALLEL", "1").strip()
    try:
        n = int(raw)
    except ValueError:
        return 1
    return max(1, n)


def _min_median_max(values: list[float]) -> tuple[float, float, float]:
    if not values:
        raise ValueError("values must be non-empty")
    s = sorted(values)
    return s[0], statistics.median(s), s[-1]


def _per_request_mib_per_s(latencies_s: list[float], mib: float) -> list[float]:
    return [mib / max(t, 1e-18) for t in latencies_s]


def _fmt_min_med_max(a: float, b: float, c: float, *, decimals: int) -> str:
    return f"min={a:.{decimals}f} med={b:.{decimals}f} max={c:.{decimals}f}"


@pytest.mark.doc_retrieval_benchmark
def test_get_document_pdf_retrieval_speed(mock_auth, test_db, capsys) -> None:
    """
    For each size: POST upload(s), GET ?file_type=pdf, assert payload size, print timing row.
    When RUN_DOC_RETRIEVAL_BENCHMARK_PARALLEL > 1, uploads and GETs run concurrently (wall time
    for the full batch); MiB/s is aggregate (parallel * file size) / wall seconds. Per size, prints
    min/median/max latency and per-request MiB/s for POST and GET; when parallel>1, also each
    worker latency (seconds, index order 0..N-1).
    """
    rows: list[str] = []
    parallel = _parallel_count()
    upload_url = f"/v0/orgs/{TEST_ORG_ID}/documents"
    auth_headers = get_auth_headers()

    for size_bytes, label in _benchmark_sizes():
        blob = _synthetic_pdf_bytes(size_bytes)
        assert len(blob) == size_bytes

        b64 = base64.b64encode(blob).decode("ascii")

        def _upload_payload(i: int) -> dict:
            return {
                "documents": [
                    {
                        "name": (
                            f"bench-{label}.pdf"
                            if parallel == 1
                            else f"bench-{label}-{i}.pdf"
                        ),
                        "content": b64,
                        "tag_ids": [],
                        "metadata": {"benchmark": "doc_get_pdf"},
                    }
                ]
            }

        def _upload_one(i: int) -> tuple[int, object, float]:
            t0 = time.perf_counter()
            r = client.post(
                upload_url,
                json=_upload_payload(i),
                headers=auth_headers,
            )
            return i, r, time.perf_counter() - t0

        def _get_one(idx_doc: tuple[int, str]) -> tuple[int, object, float]:
            idx, doc_id = idx_doc
            t0 = time.perf_counter()
            r = client.get(
                f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
                params={"file_type": "pdf"},
                headers=auth_headers,
            )
            return idx, r, time.perf_counter() - t0

        t_up0 = time.perf_counter()
        if parallel == 1:
            i0, up, upload_lat0 = _upload_one(0)
            assert i0 == 0
            upload_responses = [up]
            upload_each_s: list[float] = [upload_lat0]
        else:
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                upload_parts = list(pool.map(_upload_one, range(parallel)))
            upload_responses = [r for _, r, _ in upload_parts]
            upload_each_s = [dt for _, _, dt in upload_parts]
        upload_s = time.perf_counter() - t_up0

        for idx, up in enumerate(upload_responses):
            assert up.status_code == 200, (
                f"upload failed ({label}) #{idx}: {up.status_code} {up.text}"
            )
        doc_ids = [up.json()["documents"][0]["document_id"] for up in upload_responses]

        t_get0 = time.perf_counter()
        if parallel == 1:
            i0, resp, get_lat0 = _get_one((0, doc_ids[0]))
            assert i0 == 0
            get_responses = [resp]
            get_each_s: list[float] = [get_lat0]
        else:
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                get_parts = list(pool.map(_get_one, enumerate(doc_ids)))
            get_responses = [r for _, r, _ in get_parts]
            get_each_s = [dt for _, _, dt in get_parts]
        get_s = time.perf_counter() - t_get0

        for idx, resp in enumerate(get_responses):
            assert resp.status_code == 200, (
                f"get failed ({label}) #{idx}: {resp.status_code} {resp.text}"
            )
            content_b64 = resp.json().get("content")
            assert content_b64 is not None
            got = base64.b64decode(content_b64)
            assert len(got) == size_bytes, (
                f"size mismatch {label} #{idx}: expected {size_bytes}, got {len(got)}"
            )

        mib = size_bytes / (1024 * 1024)
        total_mib = mib * parallel
        up_mibs = total_mib / upload_s if upload_s > 0 else float("inf")
        get_mibs = total_mib / get_s if get_s > 0 else float("inf")
        par_note = f" x{parallel}" if parallel != 1 else ""
        row = (
            f"{label:>8}{par_note}  upload={upload_s:8.3f}s ({up_mibs:6.2f} MiB/s agg)  "
            f"get={get_s:8.3f}s ({get_mibs:6.2f} MiB/s agg)"
        )

        up_lat_min, up_lat_med, up_lat_max = _min_median_max(upload_each_s)
        get_lat_min, get_lat_med, get_lat_max = _min_median_max(get_each_s)
        up_rates = _per_request_mib_per_s(upload_each_s, mib)
        get_rates = _per_request_mib_per_s(get_each_s, mib)
        up_bw_min, up_bw_med, up_bw_max = _min_median_max(up_rates)
        get_bw_min, get_bw_med, get_bw_max = _min_median_max(get_rates)

        row += (
            f"\n      POST latency (s):  {_fmt_min_med_max(up_lat_min, up_lat_med, up_lat_max, decimals=3)}"
            f"\n      POST MiB/s (file): {_fmt_min_med_max(up_bw_min, up_bw_med, up_bw_max, decimals=2)}"
            f"\n      GET latency (s):   {_fmt_min_med_max(get_lat_min, get_lat_med, get_lat_max, decimals=3)}"
            f"\n      GET MiB/s (file):  {_fmt_min_med_max(get_bw_min, get_bw_med, get_bw_max, decimals=2)}"
        )
        if parallel > 1:
            up_fmt = " ".join(f"{x:.3f}" for x in upload_each_s)
            get_fmt = " ".join(f"{x:.3f}" for x in get_each_s)
            row += (
                f"\n      POST each (s): [{up_fmt}]"
                f"\n      GET each (s):  [{get_fmt}]"
            )
        rows.append(row)

    table = (
        "\n  doc GET ?file_type=pdf - JSON POST .../documents (base64 body)\n"
        "  " + "\n  ".join(rows)
        + "\n  (100MiB: RUN_DOC_RETRIEVAL_BENCHMARK_LARGE=1)\n"
        + "  (parallel: RUN_DOC_RETRIEVAL_BENCHMARK_PARALLEL, default 1)\n"
        + "  (multipart parallel benchmark: second test in this file)\n"
    )
    with capsys.disabled():
        print(table)


def _auth_headers_multipart() -> dict[str, str]:
    """Do not set Content-Type; TestClient sets multipart boundary."""
    return {"Authorization": "Bearer test_token"}


@pytest.mark.doc_retrieval_benchmark
def test_get_document_pdf_retrieval_speed_multipart(mock_auth, test_db, capsys) -> None:
    """
    Same synthetic sizes and RUN_DOC_RETRIEVAL_BENCHMARK_PARALLEL as test_get_document_pdf_retrieval_speed,
    but each upload is POST .../documents/multipart (one file part per request, raw bytes).

    Compare printed rows to the JSON/base64 benchmark for upload latency and MiB/s.
    """
    rows: list[str] = []
    parallel = _parallel_count()
    upload_url = f"/v0/orgs/{TEST_ORG_ID}/documents/multipart"
    auth_get = get_auth_headers()
    auth_mp = _auth_headers_multipart()

    for size_bytes, label in _benchmark_sizes():
        blob = _synthetic_pdf_bytes(size_bytes)
        assert len(blob) == size_bytes

        def _fname(i: int) -> str:
            return f"bench-{label}.pdf" if parallel == 1 else f"bench-{label}-{i}.pdf"

        def _upload_multipart_one(i: int) -> tuple[int, object, float]:
            fname = _fname(i)
            manifest = json.dumps(
                [
                    {
                        "name": fname,
                        "tag_ids": [],
                        "metadata": {"benchmark": "doc_get_pdf_multipart"},
                    }
                ]
            )
            t0 = time.perf_counter()
            r = client.post(
                upload_url,
                files=[("files", (fname, blob, "application/pdf"))],
                data={"manifest": manifest},
                headers=auth_mp,
            )
            return i, r, time.perf_counter() - t0

        def _get_one(idx_doc: tuple[int, str]) -> tuple[int, object, float]:
            idx, doc_id = idx_doc
            t0 = time.perf_counter()
            r = client.get(
                f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
                params={"file_type": "pdf"},
                headers=auth_get,
            )
            return idx, r, time.perf_counter() - t0

        t_up0 = time.perf_counter()
        if parallel == 1:
            i0, up, upload_lat0 = _upload_multipart_one(0)
            assert i0 == 0
            upload_responses = [up]
            upload_each_s = [upload_lat0]
        else:
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                upload_parts = list(pool.map(_upload_multipart_one, range(parallel)))
            upload_responses = [r for _, r, _ in upload_parts]
            upload_each_s = [dt for _, _, dt in upload_parts]
        upload_s = time.perf_counter() - t_up0

        for idx, up in enumerate(upload_responses):
            assert up.status_code == 200, (
                f"multipart upload failed ({label}) #{idx}: {up.status_code} {up.text}"
            )
        doc_ids = [up.json()["documents"][0]["document_id"] for up in upload_responses]

        t_get0 = time.perf_counter()
        if parallel == 1:
            i0, resp, get_lat0 = _get_one((0, doc_ids[0]))
            assert i0 == 0
            get_responses = [resp]
            get_each_s = [get_lat0]
        else:
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                get_parts = list(pool.map(_get_one, enumerate(doc_ids)))
            get_responses = [r for _, r, _ in get_parts]
            get_each_s = [dt for _, _, dt in get_parts]
        get_s = time.perf_counter() - t_get0

        for idx, resp in enumerate(get_responses):
            assert resp.status_code == 200, (
                f"get failed ({label}) #{idx}: {resp.status_code} {resp.text}"
            )
            content_b64 = resp.json().get("content")
            assert content_b64 is not None
            got = base64.b64decode(content_b64)
            assert len(got) == size_bytes, (
                f"size mismatch {label} #{idx}: expected {size_bytes}, got {len(got)}"
            )

        mib = size_bytes / (1024 * 1024)
        total_mib = mib * parallel
        up_mibs = total_mib / upload_s if upload_s > 0 else float("inf")
        get_mibs = total_mib / get_s if get_s > 0 else float("inf")
        par_note = f" x{parallel}" if parallel != 1 else ""
        row = (
            f"{label:>8}{par_note}  upload={upload_s:8.3f}s ({up_mibs:6.2f} MiB/s agg)  "
            f"get={get_s:8.3f}s ({get_mibs:6.2f} MiB/s agg)"
        )

        up_lat_min, up_lat_med, up_lat_max = _min_median_max(upload_each_s)
        get_lat_min, get_lat_med, get_lat_max = _min_median_max(get_each_s)
        up_rates = _per_request_mib_per_s(upload_each_s, mib)
        get_rates = _per_request_mib_per_s(get_each_s, mib)
        up_bw_min, up_bw_med, up_bw_max = _min_median_max(up_rates)
        get_bw_min, get_bw_med, get_bw_max = _min_median_max(get_rates)

        row += (
            f"\n      POST latency (s):  {_fmt_min_med_max(up_lat_min, up_lat_med, up_lat_max, decimals=3)}"
            f"\n      POST MiB/s (file): {_fmt_min_med_max(up_bw_min, up_bw_med, up_bw_max, decimals=2)}"
            f"\n      GET latency (s):   {_fmt_min_med_max(get_lat_min, get_lat_med, get_lat_max, decimals=3)}"
            f"\n      GET MiB/s (file):  {_fmt_min_med_max(get_bw_min, get_bw_med, get_bw_max, decimals=2)}"
        )
        if parallel > 1:
            up_fmt = " ".join(f"{x:.3f}" for x in upload_each_s)
            get_fmt = " ".join(f"{x:.3f}" for x in get_each_s)
            row += (
                f"\n      POST each (s): [{up_fmt}]"
                f"\n      GET each (s):  [{get_fmt}]"
            )
        rows.append(row)

    table = (
        "\n  doc GET ?file_type=pdf - multipart POST .../documents/multipart (compare to JSON test above)\n"
        "  " + "\n  ".join(rows)
        + "\n  (same RUN_DOC_RETRIEVAL_BENCHMARK_PARALLEL and size env vars as JSON benchmark)\n"
    )
    with capsys.disabled():
        print(table)


@pytest.mark.doc_retrieval_benchmark
def test_get_document_pdf_roundtrip_real_wax_file(mock_auth, test_db, capsys) -> None:
    """
    Upload a specific real PDF from disk, GET ?file_type=pdf, assert bytes round-trip.

    Path: default is ~/Downloads WAX_… KLUTH_GEORGE H-1.PDF; override with BENCHMARK_REAL_PDF_PATH.
    Skips if the file does not exist (e.g. CI).
    """
    pdf_path = _real_pdf_path()
    if not pdf_path.is_file():
        pytest.skip(
            f"Real PDF not found: {pdf_path} "
            "(copy the file there or set BENCHMARK_REAL_PDF_PATH to an existing .pdf)"
        )

    raw = pdf_path.read_bytes()
    assert raw.startswith(b"%PDF"), f"Not a PDF: {pdf_path}"

    b64 = base64.b64encode(raw).decode("ascii")
    upload_data = {
        "documents": [
            {
                "name": pdf_path.name,
                "content": b64,
                "tag_ids": [],
                "metadata": {"benchmark": "doc_get_pdf_real_file"},
            }
        ]
    }

    t_up0 = time.perf_counter()
    up = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/documents",
        json=upload_data,
        headers=get_auth_headers(),
    )
    upload_s = time.perf_counter() - t_up0
    assert up.status_code == 200, f"upload failed: {up.status_code} {up.text}"
    doc_id = up.json()["documents"][0]["document_id"]

    t_get0 = time.perf_counter()
    resp = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
        params={"file_type": "pdf"},
        headers=get_auth_headers(),
    )
    get_s = time.perf_counter() - t_get0

    assert resp.status_code == 200, f"get failed: {resp.status_code} {resp.text}"
    content_b64 = resp.json().get("content")
    assert content_b64 is not None
    got = base64.b64decode(content_b64)
    assert got == raw, f"round-trip mismatch: expected {len(raw)} bytes, got {len(got)}"

    mib = len(raw) / (1024 * 1024)
    line = (
        f"  real PDF {pdf_path.name!r} ({mib:.2f} MiB)  "
        f"upload={upload_s:.3f}s  get={get_s:.3f}s  "
        f"doc_id={doc_id}"
    )
    with capsys.disabled():
        print(f"\n  doc GET ?file_type=pdf (real file)\n{line}\n")
