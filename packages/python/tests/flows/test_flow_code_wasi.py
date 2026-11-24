"""The WASI runner's sandbox (the security boundary for Code / Tool Code nodes).

Runs only where the CPython WASI build is installed (``python -m
analytiq_data.flows.code_runner.python_wasi``); skipped otherwise. Checks that the guest program works
there and that the sandbox, not the guest's own checks, keeps the host out of reach.
"""

from __future__ import annotations

import time

import pytest

from analytiq_data.flows.code_runner.python_wasi import is_installed
from analytiq_data.flows.code_runner.runner import CodeExecutionError, CodeTask

pytestmark = pytest.mark.skipif(not is_installed(), reason="CPython WASI build not installed")


def _runner():
    from analytiq_data.flows.code_runner.wasi import WasiRunner

    return WasiRunner.shared()


def _task(code: str, **kw) -> CodeTask:
    return CodeTask(code=code, mode="all_items", items=[{"json": {"n": 1}}], context={}, **kw)


@pytest.mark.asyncio
async def test_runs_the_guest_program():
    res = await _runner().run(
        _task(
            "import json\ndef run(items, context):\n  print('hi')\n  return [{'n': items[0]['json']['n'] + 1}]\n"
        )
    )
    assert res.items == [{"json": {"n": 2}}]
    assert res.logs == ["hi"]


@pytest.mark.asyncio
async def test_timeout_stops_the_run():
    started = time.monotonic()
    with pytest.raises(CodeExecutionError, match="longer than 1 s"):
        await _runner().run(
            _task("def run(items, context):\n  while True:\n    pass\n", timeout_seconds=1)
        )
    # The deadline stopped it (epoch ticks are 0.1 s), not some earlier limit.
    assert 0.8 <= time.monotonic() - started < 5


@pytest.mark.asyncio
async def test_memory_limit():
    code = "def run(items, context):\n  x = bytearray(512 * 1024 * 1024)\n  return items\n"
    with pytest.raises(CodeExecutionError, match="MemoryError|out of memory"):
        await _runner().run(_task(code, memory_mb=64))


@pytest.mark.asyncio
async def test_host_files_and_environment_are_out_of_reach(monkeypatch):
    # Allow ``os`` here so the probe gets past the guest's own import hook: the sandbox must hold.
    monkeypatch.setenv("FLOW_CODE_STDLIB_ALLOW", "os")
    code = (
        "import os\n"
        "def run(items, context):\n"
        "  seen = {'env': dict(os.environ)}\n"
        "  try:\n"
        "    seen['root'] = sorted(os.listdir('/'))\n"
        "  except OSError:\n"
        "    seen['root'] = []\n"
        "  for p in ('/etc/passwd', '/Users', '/home', 'C:/Windows'):\n"
        "    seen[p] = os.path.exists(p)\n"
        "  try:\n"
        "    os.listdir('/lib')\n"
        "    fd = os.open('/lib/x.txt', os.O_CREAT | os.O_WRONLY)\n"
        "    seen['wrote'] = True\n"
        "  except OSError:\n"
        "    seen['wrote'] = False\n"
        "  return [{'json': seen}]\n"
    )
    res = await _runner().run(_task(code))
    seen = res.items[0]["json"]
    assert seen["env"] == {}
    # Only the read-only mounts: stdlib, the pure-Python zlib, the pinned packages.
    assert set(seen["root"]) <= {"lib", "sandbox-lib", "site-packages"}
    assert not any(seen[p] for p in ("/etc/passwd", "/Users", "/home", "C:/Windows"))
    assert seen["wrote"] is False


@pytest.mark.asyncio
async def test_pinned_packages_cannot_be_modified():
    code = (
        "import io\n"
        "def run(items, context):\n"
        "  import pypdf\n"
        "  try:\n"
        "    io.open('/site-packages/pypdf/__init__.py', 'a').write('x')\n"
        "    wrote = True\n"
        "  except OSError:\n"
        "    wrote = False\n"
        "  return [{'json': {'wrote': wrote}}]\n"
    )
    res = await _runner().run(_task(code))
    assert res.items[0]["json"]["wrote"] is False
