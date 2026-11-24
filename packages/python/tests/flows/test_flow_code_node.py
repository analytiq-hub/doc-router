"""Code node (``flows.code``) and its sandboxed runner.

Each runner test runs on the ``local`` runner (a plain subprocess) and, where the CPython WASI build
is installed, again on the ``wasi`` runner. The WASI sandbox's own limits are in
``test_flow_code_wasi.py``.
"""

from __future__ import annotations

import base64
from typing import Any

import pytest

import analytiq_data as ad
from analytiq_data.flows.code_runner import config as code_config
from analytiq_data.flows.code_runner.checks import CodeCheckError, check_code
from analytiq_data.flows.code_runner.python_wasi import is_installed
from analytiq_data.flows.code_runner.runner import (
    CodeExecutionError,
    CodeTask,
    get_code_runner,
    parse_result,
)
from analytiq_data.flows.nodes.code import FlowsCodeNode

_RUNNERS = ["local"] + (["wasi"] if is_installed() else [])


@pytest.fixture(params=_RUNNERS)
def runner(request, monkeypatch):
    """Run the test on the local runner, and on the WASI runner where it is installed."""
    monkeypatch.setenv("FLOW_CODE_RUNNER", request.param)
    monkeypatch.setenv("FLOW_CODE_ALLOW_UNSANDBOXED", "true")
    for name in ("FLOW_CODE_ENABLED", "FLOW_CODE_STDLIB_ALLOW", "FLOW_CODE_EXTERNAL_ALLOW"):
        monkeypatch.delenv(name, raising=False)
    return request.param


class FakeStore:
    """Stands in for GridFS: ``get_binary_stream`` / ``save_execution_binary_blob``."""

    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files = dict(files or {})
        self.written: dict[str, bytes] = {}
        self.reads: list[tuple[str, str]] = []

    async def get(self, ref: ad.flows.BinaryRef, _client: Any, *, organization_id: str) -> bytes:
        if ref.data is not None:
            return ref.data
        self.reads.append((ref.storage_id or "", organization_id))
        return self.files[ref.storage_id or ""]

    async def save(self, _client: Any, **kw: Any) -> ad.flows.BinaryRef:
        key = f"{kw['execution_id']}/{kw['node_id']}/{kw['item_index']}/{kw['property_name']}"
        self.written[f"flow_blobs:{key}"] = kw["blob"]
        return ad.flows.BinaryRef(
            mime_type=kw["mime_type"],
            file_name=kw["file_name"],
            storage_id=f"flow_blobs:{key}",
            file_size=len(kw["blob"]),
        )


@pytest.fixture
def store(monkeypatch) -> FakeStore:
    s = FakeStore()
    monkeypatch.setattr(ad.flows, "get_binary_stream", s.get)
    monkeypatch.setattr(ad.flows, "save_execution_binary_blob", s.save)
    return s


def _ctx() -> ad.flows.ExecutionContext:
    return ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="manual",
        trigger_data={"source": "test"},
        run_data={},
        analytiq_client=object(),
    )


def _item(json: dict, binary: dict | None = None) -> ad.flows.FlowItem:
    return ad.flows.FlowItem(json=json, binary=binary or {}, meta={}, paired_item=None)


async def _run(code: str, items, *, mode="all_items", on_error=None, timeout=None):
    params: dict[str, Any] = {"python_code": code, "mode": mode}
    if timeout is not None:
        params["timeout_seconds"] = timeout
    node: dict[str, Any] = {"id": "c1", "name": "Code", "parameters": params}
    if on_error:
        node["on_error"] = on_error
    ctx = _ctx()
    out = await FlowsCodeNode().execute(ctx, node, [items])
    return out[0], ctx


# ---- Static checks --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code",
    [
        "import os",
        "from subprocess import run",
        "import importlib",
        "from . import x",
        "from json import *",
        "x = __builtins__",
        "def run(items, context):\n  return (i for i in items).gi_frame",
        "def run(items, context):\n  return [].__class__.__subclasses__()",
        "def run(items, context):\n  return f'{run.__globals__}'",
        "def run(items, context):\n  raise ValueError\n  e.__traceback__.tb_frame.f_back",
        # The generator frame walk that escaped the previous runner.
        "def run(items, context):\n  h = []\n  def g():\n    yield h[0].gi_frame.f_back.f_globals\n",
        "def run(items, context)",
    ],
)
def test_check_code_refuses(code):
    with pytest.raises(CodeCheckError):
        check_code(code)


def test_check_code_accepts_allowed_modules():
    check_code("import json, re\nfrom datetime import date\ndef run(items, context):\n  return items\n")


def test_allowed_modules_follow_the_environment(monkeypatch):
    monkeypatch.setenv("FLOW_CODE_STDLIB_ALLOW", "json")
    with pytest.raises(CodeCheckError):
        check_code("import math")
    check_code("import json")


def test_allowed_modules_wildcard(monkeypatch):
    monkeypatch.setenv("FLOW_CODE_STDLIB_ALLOW", "*")
    assert code_config.allowed_modules() == ["*"]
    check_code("import os")
    monkeypatch.setenv("FLOW_CODE_STDLIB_ALLOW", "*,json")
    with pytest.raises(ValueError):
        code_config.allowed_modules()


def test_empty_allow_and_deny_use_defaults(monkeypatch):
    monkeypatch.setenv("FLOW_CODE_STDLIB_ALLOW", "")
    monkeypatch.setenv("FLOW_CODE_BUILTINS_DENY", "")
    assert "json" in code_config.allowed_modules()
    assert "eval" in code_config.builtins_deny()


# ---- Runner choice and result parsing -------------------------------------------------------------


def test_local_runner_needs_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("FLOW_CODE_RUNNER", "local")
    monkeypatch.delenv("FLOW_CODE_ALLOW_UNSANDBOXED", raising=False)
    monkeypatch.delenv("FLOW_CODE_ENABLED", raising=False)
    with pytest.raises(CodeExecutionError, match="FLOW_CODE_ALLOW_UNSANDBOXED"):
        get_code_runner()


@pytest.mark.parametrize("env", [("FLOW_CODE_RUNNER", "disabled"), ("FLOW_CODE_ENABLED", "false")])
def test_disabled_runner(monkeypatch, env):
    monkeypatch.setenv(*env)
    with pytest.raises(CodeExecutionError, match="turned off on this server"):
        get_code_runner()


def test_parse_result_without_marker_reports_stderr():
    with pytest.raises(CodeExecutionError, match="boom"):
        parse_result("hello", "Traceback ... boom")


def test_code_task_request_size_is_capped(monkeypatch):
    monkeypatch.setenv("FLOW_CODE_MAX_PAYLOAD_BYTES", "100")
    task = CodeTask(code="x" * 200, items=[], context={})
    with pytest.raises(CodeExecutionError, match="too large"):
        task.request_json()


# ---- Guest semantics ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_items_transforms_and_normalizes(runner, store):
    code = "def run(items, context):\n  return [{'n': it['json']['n'] * 2} for it in items]\n"
    out, _ = await _run(code, [_item({"n": 1}), _item({"n": 2})])
    assert [o.json for o in out] == [{"n": 2}, {"n": 4}]
    assert out[0].meta["source_node_id"] == "c1"


@pytest.mark.asyncio
async def test_context_and_logs(runner, store):
    code = (
        "import json\n"
        "def run(items, context):\n"
        "  print('hello', {'a': 1})\n"
        "  log('world')\n"
        "  return [{'json': {'node': context['node_id'], 'org': context['organization_id'],"
        " 'trigger': context['trigger']}}]\n"
    )
    out, ctx = await _run(code, [_item({})])
    assert out[0].json == {"node": "c1", "org": "org1", "trigger": {"source": "test"}}
    assert ctx.node_logs["c1"] == ['hello {"a": 1}', "world"]


@pytest.mark.asyncio
async def test_per_item_filters_and_sets_paired_item(runner, store):
    code = (
        "def run(items, context):\n"
        "  v = items[0]['json']['v']\n"
        "  return [] if v < 10 else [{'doubled': v * 2}]\n"
    )
    out, _ = await _run(code, [_item({"v": 5}), _item({"v": 12})], mode="per_item")
    assert [(o.json, o.paired_item) for o in out] == [({"doubled": 24}, 1)]


@pytest.mark.asyncio
async def test_error_fails_the_node_with_the_traceback(runner, store):
    code = "def run(items, context):\n  raise ValueError('bad input')\n"
    with pytest.raises(CodeExecutionError, match="bad input"):
        await _run(code, [_item({})])


@pytest.mark.asyncio
async def test_continue_on_fail_returns_error_items(runner, store):
    code = "def run(items, context):\n  if items[0]['json']['ok']:\n    return items\n  raise ValueError('no')\n"
    out, _ = await _run(
        code, [_item({"ok": True}), _item({"ok": False})], mode="per_item", on_error="continue"
    )
    assert out[0].json == {"ok": True}
    assert out[1].json["_error"]["message"] == "no"
    assert out[1].paired_item == 1


@pytest.mark.asyncio
async def test_static_check_runs_before_the_sandbox(runner, store):
    with pytest.raises(CodeExecutionError, match="Code refused: Import of module 'os'"):
        await _run("import os\ndef run(items, context):\n  return items\n", [_item({})])


@pytest.mark.asyncio
async def test_guest_refuses_imports_without_the_static_checks(runner):
    task = CodeTask(code="import os\ndef run(items, context):\n  return items\n", items=[], context={})
    with pytest.raises(CodeExecutionError, match="Import of module 'os' is not allowed"):
        await get_code_runner().run(task)


@pytest.mark.asyncio
async def test_denied_builtins_are_missing(runner, store):
    code = "def run(items, context):\n  open('/etc/passwd')\n  return items\n"
    with pytest.raises(CodeExecutionError, match="open"):
        await _run(code, [_item({})])


@pytest.mark.asyncio
async def test_invalid_output_is_an_error(runner, store):
    code = "def run(items, context):\n  return [{'json': {}, 'extra': 1}]\n"
    with pytest.raises(CodeExecutionError, match="mixes reserved key"):
        await _run(code, [_item({})])


@pytest.mark.asyncio
async def test_timeout(runner, store):
    code = "def run(items, context):\n  while True:\n    pass\n"
    with pytest.raises(CodeExecutionError, match="longer than"):
        await _run(code, [_item({})], timeout=1)


@pytest.mark.asyncio
async def test_tool_code_mode(runner):
    task = CodeTask(
        kind="tool_code",
        code="def run(params, context):\n  print('called')\n  return {'echo': params['q']}\n",
        params={"q": "hi"},
        context={},
    )
    res = await get_code_runner().run(task)
    assert res.tool_result == {"echo": "hi"}
    assert res.logs == ["called"]


@pytest.mark.asyncio
async def test_tool_code_must_return_a_dict(runner):
    task = CodeTask(kind="tool_code", code="def run(params, context):\n  return [1]\n", context={})
    with pytest.raises(CodeExecutionError, match="must return a dict"):
        await get_code_runner().run(task)


# ---- Files ----------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_input_file_and_store_a_new_one(runner, store):
    store.files["flow_blobs:e0/n/0/doc"] = b"hello"
    ref = ad.flows.BinaryRef(mime_type="text/plain", file_name="a.txt", storage_id="flow_blobs:e0/n/0/doc")
    code = (
        "import base64\n"
        "def run(items, context):\n"
        "  sid = items[0]['binary']['doc']['storage_id']\n"
        "  text = base64.b64decode(read_binary(sid)).decode().upper()\n"
        "  new = store_binary('text/plain', 'b.txt', base64.b64encode(text.encode()).decode())\n"
        "  return [{'json': {'text': text}, 'binary': {'doc': items[0]['binary']['doc'],"
        " 'upper': {'mime_type': 'text/plain', 'file_name': 'b.txt', 'storage_id': new}}}]\n"
    )
    out, _ = await _run(code, [_item({}, {"doc": ref})])
    assert out[0].json == {"text": "HELLO"}
    assert out[0].binary["doc"] is ref
    upper = out[0].binary["upper"]
    assert upper.storage_id == "flow_blobs:e1/c1/0/upper"
    assert store.written["flow_blobs:e1/c1/0/upper"] == b"HELLO"
    assert upper.mime_type == "text/plain" and upper.file_name == "b.txt"
    # Input files are read through the organization-scoped reader.
    assert store.reads == [("flow_blobs:e0/n/0/doc", "org1")]


@pytest.mark.asyncio
async def test_inline_input_file_is_readable(runner, store):
    ref = ad.flows.BinaryRef(mime_type="text/plain", file_name="a.txt", data=b"abc")
    code = (
        "def run(items, context):\n"
        "  return [{'json': {'b64': read_binary(items[0]['binary']['f']['storage_id'])},"
        " 'binary': items[0]['binary']}]\n"
    )
    out, _ = await _run(code, [_item({}, {"f": ref})])
    assert out[0].json["b64"] == base64.b64encode(b"abc").decode()
    assert out[0].binary["f"] is ref


@pytest.mark.asyncio
async def test_read_binary_refuses_other_ids(runner, store):
    code = "def run(items, context):\n  read_binary('files:other-org.pdf')\n  return items\n"
    with pytest.raises(CodeExecutionError, match="not a file of this node's input items"):
        await _run(code, [_item({})])
    assert store.reads == []


@pytest.mark.asyncio
async def test_output_may_not_reference_other_files(runner, store):
    code = (
        "def run(items, context):\n"
        "  return [{'json': {}, 'binary': {'x': {'mime_type': 'application/pdf',"
        " 'storage_id': 'files:other-org.pdf'}}}]\n"
    )
    with pytest.raises(CodeExecutionError, match="neither an input file"):
        await _run(code, [_item({})])


@pytest.mark.asyncio
async def test_too_large_input_file_is_not_passed(runner, store, monkeypatch):
    monkeypatch.setenv("FLOW_CODE_BINARY_READ_MAX_BYTES", "3")
    store.files["flow_blobs:k"] = b"toolarge"
    ref = ad.flows.BinaryRef(mime_type="text/plain", storage_id="flow_blobs:k", file_size=8)
    code = "def run(items, context):\n  read_binary('flow_blobs:k')\n  return items\n"
    with pytest.raises(CodeExecutionError, match="larger than the Code node's file limit"):
        await _run(code, [_item({}, {"f": ref})])
    assert store.reads == []
