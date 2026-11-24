from __future__ import annotations

"""Generic code node implementation (`flows.code`).

The user code runs in the sandbox chosen by ``FLOW_CODE_RUNNER`` (WASI by default; see
``code_runner/runner.py``), never in the worker's own interpreter, and it never reads stored files
by key:

- ``read_binary(storage_id)`` only returns the input items' own files, fetched here through the
  organization-scoped ``get_binary_stream`` and passed in (capped per file and per run).
- ``store_binary(...)`` returns a ``pending:N`` id; the files are stored here, for this run, and an
  output item may only reference an input file or a file stored by the code.
"""

import base64
import binascii
from typing import Any

import analytiq_data as ad
from analytiq_data.flows.code_runner import config as code_config
from analytiq_data.flows.code_runner.runner import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_TIMEOUT_SECONDS,
    CodeExecutionError,
    CodeTask,
    run_code_task,
)

PENDING_PREFIX = "pending:"
_INLINE_PREFIX = "input:"


class FlowsCodeNode:
    """
    Execute Python user code in the Code sandbox.

    User code must define::

        def run(items: list[dict], context: dict) -> list[dict]:
            ...

    Mode controls whether ``run`` is invoked once for all items or once per item inside the sandbox.

    The engine calls ``execute()`` once with all upstream items (``batch_execute_inputs``).
    """

    key = "flows.code"
    label = "Code (Python)"
    description = "Runs a small Python snippet to transform items."
    category = "Generic"
    palette_group = "core"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    icon_key = "code"
    type_version = 2
    batch_execute_inputs: bool = True
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["all_items", "per_item"],
                "default": "all_items",
                "description": "Run once for all input items, or once per item.",
                "x-ui-widget": "select",
                "x-ui-group": "Options",
            },
            "python_code": {
                "type": "string",
                "minLength": 1,
                "default": "def run(items, context):\n  return items\n",
                "description": "Must define def run(items: list[dict], context: dict) -> list[dict].",
                "x-ui-widget": "code",
                "x-ui-group": "Code",
            },
            "timeout_seconds": {
                "type": "number",
                "default": 30,
                "minimum": 0.0001,
                "maximum": 120,
                "description": "Wall-clock limit in seconds (default 30, max 120).",
                "x-ui-group": "Options",
                "x-ui-placeholder": "e.g. 30",
            },
        },
        "required": ["python_code"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        mode = params.get("mode", "all_items")
        if mode not in ("all_items", "per_item"):
            errs.append("parameters.mode must be 'all_items' or 'per_item'")
        if not isinstance(params.get("python_code"), str) or not params["python_code"].strip():
            errs.append("parameters.python_code must be a non-empty string")
        ts = params.get("timeout_seconds")
        if ts is not None:
            try:
                v = float(ts)
                if v <= 0 or v > MAX_TIMEOUT_SECONDS:
                    errs.append(f"parameters.timeout_seconds must be in (0, {MAX_TIMEOUT_SECONDS:g}]")
            except (TypeError, ValueError):
                errs.append("parameters.timeout_seconds must be a number")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        params = node.get("parameters") or {}
        code = params["python_code"]
        mode = params.get("mode") or "all_items"
        timeout_seconds = min(
            float(params.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS), MAX_TIMEOUT_SECONDS
        )
        continue_on_fail = (node.get("on_error") or "stop") == "continue"
        node_id = str(node.get("id") or "")

        in_items = inputs[0] if inputs else []
        known, binaries, payload_items = await _input_files(in_items, context)

        probe = in_items[0] if in_items else None
        src_start, src_exec_ms = ad.flows.timing_from_items_source_run(probe, context.run_data)
        ctx = {
            "trigger": context.trigger_data,
            "node_id": node.get("id"),
            "node_name": node.get("name"),
            "mode": context.mode,
            "nodes": ad.flows.materialize_node_data(context.run_data),
            "organization_id": context.organization_id,
            "execution_id": context.execution_id,
            "flow_id": context.flow_id,
            "flow_revid": context.flow_revid,
            "start_time": src_start,
            "execution_time": src_exec_ms,
        }
        result = await run_code_task(
            CodeTask(
                code=code,
                mode=mode,
                items=payload_items,
                context=ctx,
                continue_on_fail=continue_on_fail,
                binaries=binaries,
                timeout_seconds=timeout_seconds,
            )
        )

        if result.logs and node_id:
            context.node_logs[node_id] = [str(x) for x in result.logs]

        stored_refs: dict[int, ad.flows.BinaryRef] = {}
        out: list["ad.flows.FlowItem"] = []
        for idx, item in enumerate(result.items):
            json_payload = item.get("json") if isinstance(item.get("json"), dict) else {}
            binary_raw = item.get("binary") if isinstance(item.get("binary"), dict) else {}
            meta = dict(item.get("meta") or {})
            meta.setdefault("source_node_id", node["id"])
            meta.setdefault("item_index", idx)
            binary: dict[str, ad.flows.BinaryRef] = {}
            for name, ref in binary_raw.items():
                sid = str((ref or {}).get("storage_id") or "")
                if sid.startswith(PENDING_PREFIX):
                    binary[name] = await _stored_file(
                        context, node_id, idx, name, sid, result.stored, stored_refs
                    )
                elif sid in known:
                    binary[name] = known[sid]
                else:
                    raise CodeExecutionError(
                        f"Output item {idx}: binary['{name}'] refers to {sid!r}, which is neither "
                        "an input file nor a file stored with store_binary()"
                    )
            out.append(
                ad.flows.FlowItem(
                    json=json_payload,
                    binary=binary,
                    meta=meta,
                    paired_item=item.get("paired_item"),
                )
            )
        return [out]


async def _input_files(
    items: list["ad.flows.FlowItem"],
    context: "ad.flows.ExecutionContext",
) -> tuple[dict[str, "ad.flows.BinaryRef"], dict[str, str], list[dict[str, Any]]]:
    """The input items for the sandbox, their files by id, and the bytes it may read (capped)."""
    max_file = code_config.max_input_file_bytes()
    max_total = code_config.MAX_INPUT_TOTAL_BYTES
    known: dict[str, ad.flows.BinaryRef] = {}
    binaries: dict[str, str] = {}
    payload: list[dict[str, Any]] = []
    total = 0
    for i, it in enumerate(items):
        it = ad.flows.coerce_flow_item(it)
        row = it.to_context_dict()
        row["paired_item"] = it.paired_item
        for name, raw in (it.binary or {}).items():
            ref = ad.flows.coerce_binary_ref(raw)
            sid = ref.storage_id or f"{_INLINE_PREFIX}{i}:{name}"
            known[sid] = ref
            row["binary"].setdefault(name, {})["storage_id"] = sid
            size = ref.file_size if ref.file_size is not None else (len(ref.data) if ref.data else None)
            if sid in binaries or (size is not None and size > max_file):
                continue
            if size is not None and total + size > max_total:
                continue
            if context.analytiq_client is None and ref.data is None:
                continue
            try:
                data = await ad.flows.get_binary_stream(
                    ref, context.analytiq_client, organization_id=context.organization_id
                )
            except Exception:
                continue  # listed on the item; read_binary says it is not available
            if len(data) > max_file or total + len(data) > max_total:
                continue
            total += len(data)
            binaries[sid] = base64.b64encode(data).decode("ascii")
        payload.append(row)
    return known, binaries, payload


async def _stored_file(
    context: "ad.flows.ExecutionContext",
    node_id: str,
    item_index: int,
    name: str,
    sid: str,
    stored: list[dict[str, str]],
    done: dict[int, "ad.flows.BinaryRef"],
) -> "ad.flows.BinaryRef":
    """Store the file the code returned as ``pending:N`` (once per N) and return its reference."""
    try:
        n = int(sid[len(PENDING_PREFIX):])
        entry = stored[n]
    except (ValueError, IndexError):
        raise CodeExecutionError(f"Output item {item_index}: unknown stored file {sid!r}") from None
    if n in done:
        return done[n]
    try:
        data = base64.b64decode(entry.get("data_b64") or "", validate=True)
    except (binascii.Error, ValueError):
        raise CodeExecutionError(
            f"Output item {item_index}: stored file {sid!r} is not valid base64"
        ) from None
    ref = await ad.flows.save_execution_binary_blob(
        context.analytiq_client,
        execution_id=str(context.execution_id or ""),
        node_id=node_id,
        item_index=item_index,
        property_name=name,
        blob=data,
        mime_type=str(entry.get("mime_type") or "application/octet-stream"),
        file_name=str(entry.get("file_name") or "") or None,
    )
    done[n] = ref
    return ref
