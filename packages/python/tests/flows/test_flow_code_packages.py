"""Packages available to sandboxed Code nodes: pinned ``pypdf`` and the pure-Python ``zlib``.

The CPython WASI build has no ``zlib``; ``code_runner/sandbox_lib/zlib.py`` stands in for it so
``pypdf`` can read Flate streams. The ``zlib`` tests run on the host, comparing it with the real
module; the merge tests run on the local runner and, where installed, on the WASI runner.
"""

from __future__ import annotations

import gzip
import importlib.util
import io
import os
import random
import zipfile
import zlib
from pathlib import Path
from typing import Any

import pytest

import analytiq_data as ad
from analytiq_data.flows.code_runner import python_wasi
from analytiq_data.flows.code_runner.python_wasi import is_installed, packages_dir, packages_installed
from analytiq_data.flows.nodes.code import FlowsCodeNode

_SHIM_PATH = Path(python_wasi.__file__).with_name("sandbox_lib") / "zlib.py"


def _load_shim():
    spec = importlib.util.spec_from_file_location("sandbox_zlib", _SHIM_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


pz = _load_shim()
_rnd = random.Random(7)
_SAMPLES = [
    b"",
    b"a",
    b"hello world " * 1000,
    os.urandom(70_000),
    bytes(_rnd.choice(b"abcde") for _ in range(100_000)),
    b"".join(
        _rnd.choice([b"BT /F1 12 Tf ", b"72 712 Td ", b"(Hello) Tj ", b"ET\n", os.urandom(3)])
        for _ in range(10_000)
    ),
]


# ---- Pure-Python zlib ----------------------------------------------------------------------------


@pytest.mark.parametrize("idx", range(len(_SAMPLES)))
@pytest.mark.parametrize("level", [0, 1, 6, 9])
@pytest.mark.parametrize("strategy", [zlib.Z_DEFAULT_STRATEGY, zlib.Z_FIXED, zlib.Z_HUFFMAN_ONLY])
def test_shim_inflates_real_zlib_output(idx, level, strategy):
    data = _SAMPLES[idx]
    c = zlib.compressobj(level, zlib.DEFLATED, 15, 8, strategy)
    assert pz.decompress(c.compress(data) + c.flush()) == data


@pytest.mark.parametrize("idx", range(len(_SAMPLES)))
def test_shim_formats_and_checksums(idx):
    data = _SAMPLES[idx]
    raw = zlib.compressobj(6, zlib.DEFLATED, -15)
    assert pz.decompress(raw.compress(data) + raw.flush(), -15) == data
    gz = gzip.compress(data)
    assert pz.decompress(gz, 31) == data
    assert pz.decompress(gz, zlib.MAX_WBITS | 32) == data
    assert pz.decompress(zlib.compress(data), zlib.MAX_WBITS | 32) == data
    for wbits in (15, -15, 31):
        assert zlib.decompress(pz.compress(data, 6, wbits), wbits) == data
    assert pz.adler32(data) == zlib.adler32(data)
    assert pz.crc32(data) == zlib.crc32(data)


def test_shim_decompressobj_limit_and_trailing_data():
    data = _SAMPLES[2]
    comp = zlib.compress(data) + b"TRAILER"
    d = pz.decompressobj()
    assert d.decompress(comp, max_length=100) == data[:100]
    assert d.unconsumed_tail
    d = pz.decompressobj()
    assert d.decompress(comp) == data
    assert d.eof and d.unused_data == b"TRAILER" and not d.unconsumed_tail


def test_shim_decompressobj_byte_by_byte():
    comp = zlib.compress(b"abc" * 50)
    d = pz.decompressobj()
    assert b"".join(d.decompress(comp[i : i + 1]) for i in range(len(comp))) == b"abc" * 50
    assert d.eof


@pytest.mark.parametrize(
    "bad",
    [b"\x00\x00garbage", zlib.compress(_SAMPLES[4])[:-3] + b"xyz", zlib.compress(_SAMPLES[4])[:50]],
)
def test_shim_errors(bad):
    with pytest.raises(pz.error):
        pz.decompress(bad)


# ---- Installer ------------------------------------------------------------------------------------


def _wheel(tmp_path: Path) -> Path:
    path = tmp_path / "pkg.whl"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("demo/__init__.py", "X = 1\n")
        zf.writestr("demo/sub/mod.py", "Y = 2\n")
        zf.writestr("demo-1.0.dist-info/METADATA", "Name: demo\n")
        zf.writestr("../escape.py", "bad\n")
    return path


def test_extract_wheel_takes_only_the_package(tmp_path):
    wheel = _wheel(tmp_path)
    sha = __import__("hashlib").sha256(wheel.read_bytes()).hexdigest()
    dest = tmp_path / "out"
    python_wasi.extract_wheel(wheel, dest, "demo", sha)
    files = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    assert files == ["demo/__init__.py", "demo/sub/mod.py"]
    assert not (tmp_path / "escape.py").exists()


def test_extract_wheel_checks_the_hash(tmp_path):
    with pytest.raises(RuntimeError, match="hash mismatch"):
        python_wasi.extract_wheel(_wheel(tmp_path), tmp_path / "out", "demo", "0" * 64)


def test_packages_marker_tracks_the_pins(tmp_path):
    assert not packages_installed(tmp_path)
    packages_dir(tmp_path).mkdir()
    (packages_dir(tmp_path) / ".installed").write_text(python_wasi._packages_spec(), encoding="utf-8")
    assert packages_installed(tmp_path)
    (packages_dir(tmp_path) / ".installed").write_text("pypdf==0.0.0 x", encoding="utf-8")
    assert not packages_installed(tmp_path)


# ---- pypdf through the Code node ------------------------------------------------------------------

_HAS_PACKAGES = packages_installed()
_RUNNERS = ["local"] + (["wasi"] if is_installed() else [])

_MERGE_CODE = """
import base64
import io
from pypdf import PdfReader, PdfWriter

def run(items, context):
    writer = PdfWriter()
    for it in items:
        raw = base64.b64decode(read_binary(it["binary"]["pdf"]["storage_id"]))
        writer.append(PdfReader(io.BytesIO(raw)))
    buf = io.BytesIO()
    writer.write(buf)
    sid = store_binary("application/pdf", "merged.pdf", base64.b64encode(buf.getvalue()).decode())
    return [{"json": {"pages": len(writer.pages)},
             "binary": {"pdf": {"storage_id": sid, "mime_type": "application/pdf", "file_name": "merged.pdf"}},
             "paired_item": list(range(len(items)))}]
"""


def _page_pdf(text: str) -> bytes:
    """A one-page PDF with Flate-compressed content and object / xref streams (PyMuPDF)."""
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes(garbage=3, deflate=True, use_objstms=1)
    doc.close()
    return data


@pytest.mark.skipif(not _HAS_PACKAGES, reason="sandbox packages not installed")
@pytest.mark.parametrize("runner", _RUNNERS)
@pytest.mark.asyncio
async def test_pypdf_merges_input_pages(runner, monkeypatch):
    fitz = pytest.importorskip("fitz")
    monkeypatch.setenv("FLOW_CODE_RUNNER", runner)
    monkeypatch.setenv("FLOW_CODE_ALLOW_UNSANDBOXED", "true")
    for name in ("FLOW_CODE_ENABLED", "FLOW_CODE_STDLIB_ALLOW", "FLOW_CODE_EXTERNAL_ALLOW"):
        monkeypatch.delenv(name, raising=False)

    blobs = {f"flow_blobs:e0/split/{i}/pdf": _page_pdf(f"page {i}") for i in range(3)}
    written: dict[str, bytes] = {}

    async def fake_get(ref, _client: Any, *, organization_id: str) -> bytes:
        return blobs[ref.storage_id]

    async def fake_save(_client: Any, **kw: Any) -> ad.flows.BinaryRef:
        key = f"flow_blobs:{kw['execution_id']}/{kw['node_id']}/{kw['item_index']}/{kw['property_name']}"
        written[key] = kw["blob"]
        return ad.flows.BinaryRef(mime_type=kw["mime_type"], file_name=kw["file_name"], storage_id=key)

    monkeypatch.setattr(ad.flows, "get_binary_stream", fake_get)
    monkeypatch.setattr(ad.flows, "save_execution_binary_blob", fake_save)

    items = [
        ad.flows.FlowItem(
            json={},
            binary={"pdf": ad.flows.BinaryRef(mime_type="application/pdf", storage_id=sid, file_size=len(b))},
            meta={},
        )
        for sid, b in blobs.items()
    ]
    ctx = ad.flows.ExecutionContext(
        organization_id="org1", execution_id="e1", flow_id="f", flow_revid="r", mode="manual",
        trigger_data={}, run_data={}, analytiq_client=object(),
    )
    node = {"id": "c1", "parameters": {"python_code": _MERGE_CODE, "timeout_seconds": 10}}
    out = (await FlowsCodeNode().execute(ctx, node, [items]))[0]

    assert out[0].json == {"pages": 3}
    assert out[0].paired_item == [0, 1, 2]
    merged = fitz.open(stream=io.BytesIO(written[out[0].binary["pdf"].storage_id]), filetype="pdf")
    assert [merged[i].get_text().strip() for i in range(merged.page_count)] == ["page 0", "page 1", "page 2"]


def test_pypdf_is_allowed_by_default(monkeypatch):
    from analytiq_data.flows.code_runner.checks import check_code

    monkeypatch.delenv("FLOW_CODE_STDLIB_ALLOW", raising=False)
    check_code("import io\nfrom pypdf import PdfReader, PdfWriter\n")
