from __future__ import annotations

import os

_PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

CHILD_BOOTSTRAP = f"""
import importlib.util
import sys
import types
from pathlib import Path

root = Path({repr(_PKG_ROOT)})
for name, path in (
    ("analytiq_data", root / "analytiq_data"),
    ("analytiq_data.flows", root / "analytiq_data" / "flows"),
    ("analytiq_data.flows.code_runner", root / "analytiq_data" / "flows" / "code_runner"),
):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__path__ = [str(path)]
        sys.modules[name] = mod

spec = importlib.util.spec_from_file_location(
    "analytiq_data.flows.code_runner.child_main",
    root / "analytiq_data" / "flows" / "code_runner" / "child_main.py",
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["analytiq_data.flows.code_runner.child_main"] = mod
spec.loader.exec_module(mod)
mod.main()
"""


def minimal_env() -> dict[str, str]:
    """Environment for the isolated child (PATH only; no inherited secrets)."""
    env: dict[str, str] = {}
    if "PATH" in os.environ:
        env["PATH"] = os.environ["PATH"]
    return env
