from __future__ import annotations

import os

from .config import flow_code_env_for_child

_PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

CHILD_BOOTSTRAP = f"""
import importlib.util
import os
import sys
import types
from pathlib import Path

site_packages = os.environ.get("FLOW_CODE_SITE_PACKAGES")
if site_packages and site_packages not in sys.path:
    sys.path.insert(0, site_packages)

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
    """Environment for the isolated child (PATH + FLOW_CODE_* allowlists only)."""
    return flow_code_env_for_child()
