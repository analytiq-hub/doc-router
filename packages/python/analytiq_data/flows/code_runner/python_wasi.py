"""The CPython WebAssembly (WASI) build the ``wasi`` runner uses: pinned download and cache.

``python -m analytiq_data.flows.code_runner.python_wasi`` (also run by ``make setup-python``) downloads the
pinned release, checks its SHA-256 and extracts only ``python.wasm``, ``lib/**`` and ``LICENSE``
into ``FLOW_CODE_WASI_DIR`` (default: the repository's git-ignored ``.cache/python-wasi/<version>``).

Then it writes the guest interpreter's bytecode for both (``wasi.precompile``), so runs do not
compile every imported module's source. It also installs ``SANDBOX_PACKAGES`` (pinned pure-Python wheels, SHA-256 checked, no dependencies)
into ``<root>/site-packages``, which the sandbox sees read-only at ``/site-packages``.

Images bake the same files in at build time. Nothing is downloaded at run time.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

PYTHON_WASI_VERSION = "3.15.2"
PYTHON_WASI_URL = (
    "https://github.com/brettcannon/cpython-wasi-build/releases/download/"
    f"v{PYTHON_WASI_VERSION}/python-{PYTHON_WASI_VERSION}-wasi_sdk-33.zip"
)
PYTHON_WASI_SHA256 = "b8a63559c56760bbdc310dedb74fd69d10bcbafae26b705bea0ad353ad256888"
_MAX_ZIP_BYTES = 200 << 20

#: Pure-Python packages available to sandboxed code (importable when allowed, see ``config.py``).
#: (import name, version, wheel URL, wheel SHA-256). Each must have no runtime dependencies.
SANDBOX_PACKAGES: tuple[tuple[str, str, str, str], ...] = (
    (
        "pypdf",
        "7.0.1",
        "https://files.pythonhosted.org/packages/d5/a9/ae11deef21eaac5113f8c3848da1c42423b7abeca0abc349bfec7abf4c4e/"
        "pypdf-7.0.1-py3-none-any.whl",
        "6131b764b046282357037309e7ef2a1b7679d4a5c53eed3db2bfbf7c673ddc2b",
    ),
)
_PACKAGES_MARKER = ".installed"
_PRECOMPILED_MARKER = ".precompiled"

_REPO_ROOT = Path(__file__).resolve().parents[5]


def wasi_dir() -> Path:
    """Directory with ``python.wasm`` and ``lib/python3.x``."""
    raw = os.environ.get("FLOW_CODE_WASI_DIR", "").strip()
    if raw:
        return Path(raw)
    return _REPO_ROOT / ".cache" / "python-wasi" / PYTHON_WASI_VERSION


def is_installed(root: Path | None = None) -> bool:
    root = root or wasi_dir()
    return (root / "python.wasm").is_file() and (root / "lib").is_dir()


def packages_dir(root: Path | None = None) -> Path:
    """Pinned pure-Python packages for the sandbox (preopened read-only at ``/site-packages``)."""
    return (root or wasi_dir()) / "site-packages"


def _packages_spec() -> str:
    return "\n".join(f"{name}=={version} {sha}" for name, version, _url, sha in SANDBOX_PACKAGES)


def packages_installed(root: Path | None = None) -> bool:
    marker = packages_dir(root) / _PACKAGES_MARKER
    try:
        return marker.read_text(encoding="utf-8") == _packages_spec()
    except OSError:
        return False


def _safe_member(name: str) -> PurePosixPath | None:
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or "\\" in name or name.endswith("/"):
        return None
    return p


def extract_wheel(wheel_path: Path, dest: Path, name: str, sha256: str) -> None:
    """Check a wheel's hash, then extract only its ``<name>/`` package into ``dest``."""
    digest = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
    if digest != sha256:
        raise RuntimeError(f"{name} wheel hash mismatch: {digest} (expected {sha256})")
    with zipfile.ZipFile(wheel_path) as zf:
        for info in zf.infolist():
            p = _safe_member(info.filename)
            if p is None or p.parts[:1] != (name,):
                continue
            if (info.external_attr >> 16) & 0o170000 == 0o120000:  # symbolic link
                continue
            out_path = dest.joinpath(*p.parts)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(out_path, "wb") as out:
                shutil.copyfileobj(src, out)
    if not (dest / name / "__init__.py").is_file():
        raise RuntimeError(f"{name} wheel has no {name}/__init__.py")


def install_packages(root: Path | None = None) -> Path:
    """Install ``SANDBOX_PACKAGES`` into ``<root>/site-packages`` (replaced)."""
    root = root or wasi_dir()
    target = packages_dir(root)
    staging = Path(tempfile.mkdtemp(prefix="sandbox-packages-", dir=root))
    try:
        for name, _version, url, sha in SANDBOX_PACKAGES:
            wheel = staging / f"{name}.whl"
            _download(url, wheel)
            extract_wheel(wheel, staging, name, sha)
            wheel.unlink()
        (staging / _PACKAGES_MARKER).write_text(_packages_spec(), encoding="utf-8")
        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return target


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as resp, open(dest, "wb") as out:
        total = 0
        while chunk := resp.read(1 << 20):
            total += len(chunk)
            if total > _MAX_ZIP_BYTES:
                raise RuntimeError(f"download is larger than expected: {url}")
            out.write(chunk)


def _wanted(name: str) -> bool:
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or "\\" in name:
        return False
    return name in ("python.wasm", "LICENSE") or (
        p.parts[:1] == ("lib",) and not name.endswith("/")
    )


def extract(zip_path: Path, root: Path) -> None:
    """Check the archive's hash, then extract the wanted members into ``root`` (replaced)."""
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    if digest != PYTHON_WASI_SHA256:
        raise RuntimeError(
            f"python-wasi archive hash mismatch: {digest} (expected {PYTHON_WASI_SHA256})"
        )
    staging = Path(
        tempfile.mkdtemp(prefix="python-wasi-", dir=root.parent if root.parent.exists() else None)
    )
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                if info.is_dir() or not _wanted(info.filename):
                    continue
                if (info.external_attr >> 16) & 0o170000 == 0o120000:  # symbolic link
                    continue
                dest = staging.joinpath(*PurePosixPath(info.filename).parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
        if not is_installed(staging):
            raise RuntimeError("python-wasi archive has no python.wasm or lib/")
        if root.exists():
            shutil.rmtree(root)
        staging.rename(root)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def install(root: Path | None = None, *, force: bool = False) -> Path:
    root = root or wasi_dir()
    if force or not is_installed(root):
        root.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "python-wasi.zip"
            _download(PYTHON_WASI_URL, zip_path)
            extract(zip_path, root)
    if force or not packages_installed(root):
        install_packages(root)
    marker = root / _PRECOMPILED_MARKER
    spec = f"{PYTHON_WASI_VERSION}\n{_packages_spec()}"
    if force or not marker.is_file() or marker.read_text(encoding="utf-8") != spec:
        from .wasi import precompile  # needs wasmtime; imported only here

        precompile(root)
        marker.write_text(spec, encoding="utf-8")
    return root


def main(argv: list[str]) -> int:
    force = "--force" in argv
    root = install(force=force)
    pkgs = ", ".join(f"{n}=={v}" for n, v, _u, _s in SANDBOX_PACKAGES)
    print(f"CPython WASI {PYTHON_WASI_VERSION} in {root} (sandbox packages: {pkgs})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
