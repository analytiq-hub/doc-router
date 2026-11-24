"""``FLOW_CODE_RUNNER=local``: the guest program in a plain subprocess.

**Not a sandbox**: the code runs as the worker's operating-system user, with the same restricted
namespace as in the sandbox but nothing below it. ``get_code_runner`` refuses it unless
``FLOW_CODE_ALLOW_UNSANDBOXED=true``. For development, tests, and single-tenant installs where every
flow editor is trusted and needs compiled packages (``FLOW_CODE_EXTERNAL_ALLOW``).
"""

from __future__ import annotations

import asyncio
import os
import sys
import sysconfig

from .python_wasi import packages_dir
from .runner import CodeExecutionError, CodeResult, CodeTask, guest_source, parse_result


class LocalSubprocessRunner:
    name = "local"

    async def run(self, task: CodeTask) -> CodeResult:
        site_packages = packages_dir()
        request = task.request_json(sys_path=[str(site_packages)] if site_packages.is_dir() else [])
        source = guest_source()
        if (os.environ.get("FLOW_CODE_EXTERNAL_ALLOW") or "").strip():
            # ``-I -S`` leaves site-packages off sys.path: add it so allowed third-party modules import.
            source = _with_site_packages(source)
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-S",
            "-c",
            source,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={"PATH": os.environ.get("PATH", "")},
        )
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(request), timeout=task.timeout_seconds
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise CodeExecutionError(
                f"The code took longer than {task.timeout_seconds:g} s and was stopped"
            ) from None
        return parse_result(
            out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), kind=task.kind
        )


def _with_site_packages(source: str) -> str:
    purelib = sysconfig.get_path("purelib")
    platlib = sysconfig.get_path("platlib")
    prefix = "import sys\n" + "".join(
        f"sys.path.append({p!r})\n" for p in dict.fromkeys((purelib, platlib))
    )
    return prefix + source
