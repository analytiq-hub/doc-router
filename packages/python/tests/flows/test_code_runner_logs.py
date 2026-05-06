from __future__ import annotations

import pytest

import analytiq_data as ad


@pytest.mark.asyncio
async def test_run_python_code_captures_print_logs() -> None:
    code = """
def run(items, context):
  print("hello", 123)
  log("world")
  return items
"""
    items, logs = await ad.flows.run_python_code(code=code, items=[{"a": 1}], context={}, timeout_seconds=2)
    assert items == [{"a": 1}]
    # The runner stores the trailing newline in each entry (stdout-style).
    assert any("hello 123" in s for s in logs)
    assert any("world" in s for s in logs)

