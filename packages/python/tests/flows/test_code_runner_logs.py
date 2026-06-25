from __future__ import annotations

import pytest

import analytiq_data as ad


def _item(json_payload: dict) -> dict:
    return {"json": json_payload, "binary": {}, "meta": {}}


@pytest.mark.asyncio
async def test_run_python_code_captures_print_logs() -> None:
    code = """
def run(items, context):
  print("hello", 123)
  log("world")
  return items
"""
    items, logs = await ad.flows.run_python_code(
        code=code,
        items=[_item({"a": 1})],
        context={},
        timeout_seconds=5,
    )
    assert items == [_item({"a": 1})]
    assert any("hello" in s and "123" in s for s in logs)
    assert any("world" in s for s in logs)
