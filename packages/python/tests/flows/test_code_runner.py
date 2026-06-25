from __future__ import annotations

import pytest

import analytiq_data as ad
from analytiq_data.flows.code_runner.analyzer import SecurityValidationError, TaskAnalyzer
from analytiq_data.flows.code_runner.bootstrap import minimal_env
from analytiq_data.flows.code_runner.config import SecurityConfig
from analytiq_data.flows.code_runner.validation import CodeValidationError, validate_code_output


def test_validate_code_output_wraps_plain_dicts() -> None:
    out = validate_code_output([{"a": 1}, {"b": 2}])
    assert out == [{"json": {"a": 1}}, {"json": {"b": 2}}]


def test_validate_code_output_rejects_mixed_batch() -> None:
    with pytest.raises(CodeValidationError):
        validate_code_output([{"json": {"a": 1}}, {"patient_id": "p1"}])


def test_validate_code_output_requires_binary_storage_id() -> None:
    with pytest.raises(CodeValidationError):
        validate_code_output(
            [{"json": {}, "binary": {"pdf": {"mime_type": "application/pdf"}}}]
        )


def test_analyzer_blocks_os_import() -> None:
    config = SecurityConfig.from_env()
    with pytest.raises(SecurityValidationError):
        TaskAnalyzer().validate("import os\n\ndef run(items, context):\n  return items\n", config)


@pytest.mark.asyncio
async def test_run_python_code_per_item_filters() -> None:
    code = """
def run(items, context):
    value = items[0]["json"].get("value", 0)
    if value < 10:
        return []
    return [{"doubled": value * 2}]
"""
    items = [
        {"json": {"value": 5}, "binary": {}, "meta": {}},
        {"json": {"value": 12}, "binary": {}, "meta": {}},
    ]
    out, _logs = await ad.flows.run_python_code(
        code=code,
        items=items,
        context={},
        mode="per_item",
        timeout_seconds=5,
    )
    assert len(out) == 1
    assert out[0]["json"]["doubled"] == 24
    assert out[0]["paired_item"] == 1


def test_minimal_env_forwards_flow_code_allowlists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOW_CODE_EXTERNAL_ALLOW", "fitz")
    monkeypatch.setenv("SECRET_TOKEN", "must-not-leak")
    env = minimal_env()
    assert env.get("FLOW_CODE_EXTERNAL_ALLOW") == "fitz"
    assert env.get("FLOW_CODE_SITE_PACKAGES")
    assert "SECRET_TOKEN" not in env


def test_security_config_empty_stdlib_allow_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOW_CODE_STDLIB_ALLOW", "")
    config = SecurityConfig.from_env()
    assert "json" in config.stdlib_allow
    assert "re" in config.stdlib_allow


def test_security_config_empty_builtins_deny_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOW_CODE_BUILTINS_DENY", "")
    config = SecurityConfig.from_env()
    assert "eval" in config.builtins_deny
    assert "exec" in config.builtins_deny


@pytest.mark.asyncio
async def test_run_python_code_external_allow_fitz(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fitz")
    monkeypatch.setenv("FLOW_CODE_EXTERNAL_ALLOW", "fitz")
    code = """
import fitz

def run(items, context):
    return [{"json": {"fitz_version": fitz.version[0]}}]
"""
    out, _logs = await ad.flows.run_python_code(
        code=code,
        items=[{"json": {}, "binary": {}, "meta": {}}],
        context={},
        timeout_seconds=5,
    )
    assert out[0]["json"]["fitz_version"]
