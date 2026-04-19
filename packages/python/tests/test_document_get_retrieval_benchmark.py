"""
Benchmark GET /v0/orgs/{org}/documents/{id}?file_type=pdf (full JSON + base64 body).

Uploads synthetic PDF-shaped blobs, then measures wall-clock time for one retrieval per size.

Default run: 0.1 MiB and 1 MiB only (CI-friendly).
10 MiB and 100 MiB: set RUN_DOC_RETRIEVAL_BENCHMARK_LARGE=1 (high memory; ~133 MiB JSON for upload at 100 MiB).

Show timings: pytest -s packages/python/tests/test_document_get_retrieval_benchmark.py

Real PDF round-trip (optional): place the file at the default path below or set BENCHMARK_REAL_PDF_PATH.
If the file is missing, the test is skipped (CI-friendly).
"""

from __future__ import annotations

import base64
import os
import time
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
    ]
    env = os.environ.get("RUN_DOC_RETRIEVAL_BENCHMARK_LARGE", "").strip().lower()
    if env in ("1", "true", "yes", "all"):
        sizes.extend(
            [
                (10 * 1024 * 1024, "10MiB"),
                (100 * 1024 * 1024, "100MiB"),
            ]
        )
    return sizes


@pytest.mark.doc_retrieval_benchmark
def test_get_document_pdf_retrieval_speed(mock_auth, test_db, capsys) -> None:
    """
    For each size: POST upload, GET ?file_type=pdf, assert payload size, print timing row.
    """
    rows: list[str] = []
    for size_bytes, label in _benchmark_sizes():
        blob = _synthetic_pdf_bytes(size_bytes)
        assert len(blob) == size_bytes

        b64 = base64.b64encode(blob).decode("ascii")
        upload_data = {
            "documents": [
                {
                    "name": f"bench-{label}.pdf",
                    "content": b64,
                    "tag_ids": [],
                    "metadata": {"benchmark": "doc_get_pdf"},
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
        assert up.status_code == 200, f"upload failed ({label}): {up.status_code} {up.text}"
        doc_id = up.json()["documents"][0]["document_id"]

        t_get0 = time.perf_counter()
        resp = client.get(
            f"/v0/orgs/{TEST_ORG_ID}/documents/{doc_id}",
            params={"file_type": "pdf"},
            headers=get_auth_headers(),
        )
        get_s = time.perf_counter() - t_get0

        assert resp.status_code == 200, f"get failed ({label}): {resp.status_code} {resp.text}"
        content_b64 = resp.json().get("content")
        assert content_b64 is not None
        got = base64.b64decode(content_b64)
        assert len(got) == size_bytes, f"size mismatch {label}: expected {size_bytes}, got {len(got)}"

        mib = size_bytes / (1024 * 1024)
        up_mibs = mib / upload_s if upload_s > 0 else float("inf")
        get_mibs = mib / get_s if get_s > 0 else float("inf")
        row = (
            f"{label:>8}  upload={upload_s:8.3f}s ({up_mibs:6.2f} MiB/s)  "
            f"get={get_s:8.3f}s ({get_mibs:6.2f} MiB/s)"
        )
        rows.append(row)

    table = (
        "\n  doc GET ?file_type=pdf retrieval benchmark\n"
        "  " + "\n  ".join(rows)
        + "\n  (10MiB/100MiB: RUN_DOC_RETRIEVAL_BENCHMARK_LARGE=1)\n"
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
