"""``FLOW_CODE_RUNNER=wasi``: the guest program in CPython compiled to WebAssembly (the security boundary).

``wasmtime`` runs ``python.wasm`` in the worker process. The guest gets nothing from the host but:
the standard library, preopened **read-only** at ``/lib``; the pinned pure-Python
``SANDBOX_PACKAGES``, **read-only** at ``/site-packages``; ``sandbox_lib/`` (a pure-Python
``zlib``, which the WASI build lacks), **read-only** at ``/sandbox-lib``; stdin (the request, from a temporary
file); stdout (captured in memory, capped); argv. No environment, no other files, no sockets, no
clock beyond WASI's. Limits: linear memory (store limits) and a wall-clock deadline (epoch
interruption, ticked by one background thread per process). No fuel (instruction budget): it ran
out about 4x sooner than the deadline, stopping legitimate work early, and slows every run.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading
import time
from pathlib import Path

from .python_wasi import is_installed, packages_dir, wasi_dir
from .runner import CodeExecutionError, CodeResult, CodeTask, guest_source, parse_result

_EPOCH_TICK_SECONDS = 0.1
#: Repository-owned modules the WASI build lacks (a pure-Python ``zlib``), read-only in the guest.
_SANDBOX_LIB = Path(__file__).with_name("sandbox_lib")
_MAX_STDOUT_BYTES = 64 << 20


class WasiRunner:
    name = "wasi"
    _shared: WasiRunner | None = None
    _shared_lock = threading.Lock()

    def __init__(self, root: Path | None = None) -> None:
        import wasmtime

        self._wasmtime = wasmtime
        self._root = root or wasi_dir()
        if not is_installed(self._root):
            raise CodeExecutionError(
                f"The Code node's Python (WebAssembly) is not installed in {self._root}: run "
                "`python -m analytiq_data.flows.code_runner.python_wasi` (or `make setup-python`)"
            )
        config = wasmtime.Config()
        config.epoch_interruption = True
        cache_dir = self._root / ".compiled"
        self._engine = wasmtime.Engine(config)
        self._module = self._load_module(cache_dir)
        self._ticker = threading.Thread(target=self._tick, name="flow-code-epoch", daemon=True)
        self._ticker.start()

    @classmethod
    def shared(cls) -> WasiRunner:
        """One runner per process: compiling ``python.wasm`` takes seconds, so it is done once."""
        with cls._shared_lock:
            if cls._shared is None:
                cls._shared = cls()
            return cls._shared

    def _load_module(self, cache_dir: Path):
        """The compiled module, from a file cached next to ``python.wasm`` when it is still valid."""
        wasmtime = self._wasmtime
        wasm = self._root / "python.wasm"
        cached = cache_dir / f"python-{wasm.stat().st_size}-{int(wasm.stat().st_mtime)}-epoch.cwasm"
        if cached.is_file():
            try:
                return wasmtime.Module.deserialize_file(self._engine, str(cached))
            except Exception:
                cached.unlink(missing_ok=True)
        module = wasmtime.Module.from_file(self._engine, str(wasm))
        try:
            cache_dir.mkdir(exist_ok=True)
            tmp = cached.with_suffix(".tmp")
            tmp.write_bytes(module.serialize())
            os.replace(tmp, cached)
        except OSError:
            pass  # read-only image: compile on each start
        return module

    def _tick(self) -> None:
        while True:
            time.sleep(_EPOCH_TICK_SECONDS)
            self._engine.increment_epoch()

    async def run(self, task: CodeTask) -> CodeResult:
        sys_path = ["/sandbox-lib"]
        if packages_dir(self._root).is_dir():
            sys_path.append("/site-packages")
        request = task.request_json(sys_path=sys_path)
        return await asyncio.to_thread(self._run_sync, task, request)

    def _run_sync(self, task: CodeTask, request: bytes) -> CodeResult:
        wasmtime = self._wasmtime
        out = bytearray()
        overflow = False

        def on_stdout(data: bytes) -> None:
            nonlocal overflow
            if len(out) + len(data) > _MAX_STDOUT_BYTES:
                overflow = True
                return
            out.extend(data)

        err = bytearray()

        def on_stderr(data: bytes) -> None:
            if len(err) < 64 << 10:
                err.extend(data[: (64 << 10) - len(err)])

        with tempfile.TemporaryDirectory(prefix="flow-code-") as tmp:
            stdin_path = Path(tmp) / "request.json"
            stdin_path.write_bytes(request)

            wasi = wasmtime.WasiConfig()
            wasi.argv = ["python", "-I", "-B", "-c", guest_source()]
            wasi.preopen_dir(str(self._root / "lib"), "/lib", fs_mutable=False)
            wasi.preopen_dir(str(_SANDBOX_LIB), "/sandbox-lib", fs_mutable=False)
            site_packages = packages_dir(self._root)
            if site_packages.is_dir():
                wasi.preopen_dir(str(site_packages), "/site-packages", fs_mutable=False)
            wasi.stdin_file = str(stdin_path)
            wasi.stdout_custom = on_stdout
            wasi.stderr_custom = on_stderr

            store = wasmtime.Store(self._engine)
            store.set_limits(memory_size=task.memory_mb << 20)
            store.set_epoch_deadline(max(1, int(task.timeout_seconds / _EPOCH_TICK_SECONDS)))
            store.set_wasi(wasi)

            linker = wasmtime.Linker(self._engine)
            linker.define_wasi()
            try:
                instance = linker.instantiate(store, self._module)
                instance.exports(store)["_start"](store)
            except wasmtime.ExitTrap as e:
                if e.code != 0 and not out:
                    raise CodeExecutionError(
                        f"The code runner exited with code {e.code}: {err.decode('utf-8', 'replace')[-2000:]}"
                    ) from None
            except wasmtime.Trap as e:
                raise CodeExecutionError(_trap_message(e, task)) from None
            except wasmtime.WasmtimeError as e:
                raise CodeExecutionError(_trap_message(e, task)) from None

        if overflow:
            raise CodeExecutionError(
                f"The code's output is larger than {_MAX_STDOUT_BYTES >> 20} MB"
            )
        return parse_result(
            out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), kind=task.kind
        )


def _trap_message(e: Exception, task: CodeTask) -> str:
    text = str(e)
    low = text.lower()
    if "interrupt" in low or "epoch" in low:
        return f"The code took longer than {task.timeout_seconds:g} s and was stopped"
    if "memory" in low or "out of bounds" in low:
        return f"The code ran out of memory (limit {task.memory_mb} MB)"
    return f"The code runner stopped: {text.splitlines()[0] if text else type(e).__name__}"


_PRECOMPILE_SOURCE = r"""
import compileall, re, sys
skip = re.compile(r"/(test|tests|idlelib|tkinter|turtledemo|lib2to3)/")
for top in sys.argv[1:]:
    compileall.compile_dir(top, quiet=2, rx=skip, workers=1)
print("precompiled")
"""


def precompile(root: Path | None = None) -> None:
    """Write the guest interpreter's bytecode for its stdlib and ``SANDBOX_PACKAGES``.

    Runs once at install time (``python_wasi.install``), with ``/lib`` and ``/site-packages``
    writable for this step only. Runs then load ``.pyc`` files instead of compiling the source of
    every module they import (which the read-only sandbox could not cache). Also leaves the
    compiled ``python.wasm`` module cached for the workers.
    """
    runner = WasiRunner(root)
    wasmtime = runner._wasmtime
    out = bytearray()
    tops = ["/lib"]
    wasi = wasmtime.WasiConfig()
    wasi.preopen_dir(str(runner._root / "lib"), "/lib", fs_mutable=True)
    site_packages = packages_dir(runner._root)
    if site_packages.is_dir():
        wasi.preopen_dir(str(site_packages), "/site-packages", fs_mutable=True)
        tops.append("/site-packages")
    wasi.argv = ["python", "-I", "-c", _PRECOMPILE_SOURCE, *tops]
    wasi.stdout_custom = out.extend
    wasi.stderr_custom = out.extend
    store = wasmtime.Store(runner._engine)
    store.set_epoch_deadline(int(1800 / _EPOCH_TICK_SECONDS))
    store.set_wasi(wasi)
    linker = wasmtime.Linker(runner._engine)
    linker.define_wasi()
    try:
        linker.instantiate(store, runner._module).exports(store)["_start"](store)
    except wasmtime.ExitTrap as e:
        if e.code != 0:
            raise CodeExecutionError(f"precompile failed: {out.decode('utf-8', 'replace')[-2000:]}") from None
    if b"precompiled" not in out:
        raise CodeExecutionError(f"precompile failed: {out.decode('utf-8', 'replace')[-2000:]}")
