from __future__ import annotations

"""
Expression / templating helpers for flows.

Only a small subset is implemented today:
- `materialize_node_data(run_data)` used to expose prior node outputs as plain JSON.
- Expression evaluation and parameter resolution (`resolve_parameters`) for `=`-prefixed strings.

See `docs/flows.md` §20.3 / §20.4.
"""

import ast
from typing import Any

import analytiq_data as ad


class ExpressionError(ValueError):
    """Raised when an expression fails validation or evaluation."""


_ALLOWED_AST_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Attribute,
    ast.Subscript,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Slice,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Is,
    ast.IsNot,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
)


def timing_from_items_source_run(
    item: ad.flows.FlowItem | None,
    run_data: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """
    `start_time` and `execution_time_ms` from the **producing** node for this item
    (`item.meta[\"source_node_id\"]` → `run_data[node_id]`).

    Returned tuple is `(start_time, execution_time)` where ``execution_time`` is
    the engine's ``execution_time_ms`` value (ms). Missing data → ``(None, None)``.
    """

    if item is None or not run_data:
        return (None, None)
    meta = item.meta if isinstance(item.meta, dict) else {}
    sid = meta.get("source_node_id")
    if not isinstance(sid, str) or not sid:
        return (None, None)
    entry = run_data.get(sid)
    if not isinstance(entry, dict):
        return (None, None)
    return (entry.get("start_time"), entry.get("execution_time_ms"))


def _rewrite_vars(expr: str) -> str:
    """
    Rewrite n8n-ish `$json` / `$node` to valid Python identifiers, but only when
    those sequences appear *outside* Python string literals.

    We intentionally do not try to be a full Python lexer; the goal is simply to
    avoid rewriting inside quoted strings (e.g. "literal $json").
    """

    out: list[str] = []
    i = 0
    n = len(expr)

    quote: str | None = None  # "'" | '"' when inside a string
    triple = False
    while i < n:
        ch = expr[i]

        if quote is None:
            if ch in ("'", '"'):
                # Enter string; detect triple quotes.
                if i + 2 < n and expr[i : i + 3] == ch * 3:
                    quote = ch
                    triple = True
                    out.append(ch * 3)
                    i += 3
                    continue
                quote = ch
                triple = False
                out.append(ch)
                i += 1
                continue

            if expr.startswith("$execution_id", i):
                out.append("_execution['execution_id']")
                i += len("$execution_id")
                continue
            if expr.startswith("$flow_revid", i):
                out.append("_execution['flow_revid']")
                i += len("$flow_revid")
                continue
            if expr.startswith("$flow_id", i):
                out.append("_execution['flow_id']")
                i += len("$flow_id")
                continue
            if expr.startswith("$execution_time", i):
                out.append("_execution_time")
                i += len("$execution_time")
                continue
            if expr.startswith("$execution", i):
                out.append("_execution")
                i += len("$execution")
                continue
            if expr.startswith("$start_time", i):
                out.append("_start_time")
                i += len("$start_time")
                continue
            if expr.startswith("$json", i):
                out.append("_json")
                i += 5
                continue
            if expr.startswith("$node", i):
                out.append("_node")
                i += 5
                continue
            if expr.startswith("$binary", i):
                out.append("_binary")
                i += 7
                continue
            if expr.startswith("$input", i):
                out.append("_input")
                i += 6
                continue
            if expr.startswith("$item", i):
                out.append("_item")
                i += 5
                continue
            if expr.startswith("$items", i):
                out.append("_items")
                i += 6
                continue

            out.append(ch)
            i += 1
            continue

        # Inside a string.
        if not triple and ch == "\\":
            # Preserve escapes in normal strings.
            if i + 1 < n:
                out.append(expr[i : i + 2])
                i += 2
            else:
                out.append(ch)
                i += 1
            continue

        if triple:
            if i + 2 < n and expr[i : i + 3] == quote * 3:
                out.append(quote * 3)
                i += 3
                quote = None
                triple = False
                continue
            out.append(ch)
            i += 1
            continue

        # Single-quoted string end.
        if ch == quote:
            out.append(ch)
            i += 1
            quote = None
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def _validate_expr_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST_NODES):
            raise ExpressionError(f"Unsupported expression syntax: {type(node).__name__}")
        if isinstance(node, ast.Name):
            if node.id.startswith("__"):
                raise ExpressionError("Names starting with '__' are not allowed in expressions")


def _materialize_binary(binary: dict[str, ad.flows.BinaryRef]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (binary or {}).items():
        out[k] = {
            "mime_type": v.mime_type,
            "file_name": v.file_name,
            # Intentionally omit raw `data` bytes from expression context.
            "data": None,
            "storage_id": v.storage_id,
        }
    return out


def _materialize_item(it: ad.flows.FlowItem) -> dict[str, Any]:
    return {
        "json": it.json,
        "binary": _materialize_binary(it.binary or {}),
        "meta": it.meta,
        "paired_item": it.paired_item,
    }


def materialize_input_context(
    inputs: list[list[ad.flows.FlowItem]] | None,
    *,
    input_index: int | None = None,
    item_index: int | None = None,
) -> dict[str, Any]:
    """
    Build an n8n-ish `$input` object for expression evaluation.

    Shape:
    {
      "all":   [ [item, ...], [item, ...], ... ],   # all input slots
      "item":  {json,binary,meta,paired_item} | None,  # current item (if in per-item mode)
      "input_index": int | None,
      "item_index":  int | None,
    }
    """

    slots = inputs or []
    all_slots = [[_materialize_item(it) for it in slot] for slot in slots]
    current = None
    if input_index is not None and item_index is not None:
        if 0 <= input_index < len(slots) and 0 <= item_index < len(slots[input_index]):
            current = _materialize_item(slots[input_index][item_index])
    return {
        "all": all_slots,
        "item": current,
        "input_index": input_index,
        "item_index": item_index,
    }


def eval_expression(
    expr: str,
    *,
    item: ad.flows.FlowItem | None,
    run_data: dict[str, Any],
    input_context: dict[str, Any] | None = None,
    execution_refs: dict[str, Any] | None = None,
) -> Any:
    """
    Evaluate a single expression string (without leading '=') against the current item and run_data.
    """

    expr = expr.strip()
    rewritten = _rewrite_vars(expr)
    try:
        tree = ast.parse(rewritten, mode="eval")
    except Exception as e:
        raise ExpressionError(f"Invalid expression: {e}") from e

    _validate_expr_ast(tree)
    code = compile(tree, "<flow-expr>", "eval")

    refs = execution_refs if execution_refs is not None else {}
    src_start, src_exec_ms = timing_from_items_source_run(item, run_data)
    env = {
        "_json": (item.json if item is not None else {}),
        "_binary": (_materialize_binary(item.binary or {}) if item is not None else {}),
        "_node": materialize_node_data(run_data),
        "_execution": dict(refs) if refs else {},
        "_start_time": src_start,
        "_execution_time": src_exec_ms,
        # n8n-ish additions:
        "_input": (input_context or {"all": [], "item": None, "input_index": None, "item_index": None}),
        "_item": (_materialize_item(item) if item is not None else None),
        # Convenience: a JSON-only view of prior node outputs by node id.
        "_items": materialize_node_data(run_data),
    }
    try:
        return eval(code, {"__builtins__": {}}, env)
    except Exception as e:
        raise ExpressionError(str(e)) from e


def resolve_parameters(
    params: Any,
    *,
    item: ad.flows.FlowItem | None,
    run_data: dict[str, Any],
    input_context: dict[str, Any] | None = None,
    execution_refs: dict[str, Any] | None = None,
) -> Any:
    """
    Recursively resolve parameters, evaluating any string value that starts with '='.
    """

    if isinstance(params, str):
        if params.startswith("="):
            return eval_expression(
                params[1:],
                item=item,
                run_data=run_data,
                input_context=input_context,
                execution_refs=execution_refs,
            )
        return params
    if isinstance(params, list):
        return [
            resolve_parameters(x, item=item, run_data=run_data, input_context=input_context, execution_refs=execution_refs)
            for x in params
        ]
    if isinstance(params, dict):
        return {
            k: resolve_parameters(v, item=item, run_data=run_data, input_context=input_context, execution_refs=execution_refs)
            for k, v in params.items()
        }
    return params


def materialize_node_data(run_data: dict[str, Any]) -> dict[str, Any]:
    """
    Convert engine `run_data` (which may contain `FlowItem` objects) into a JSON-only
    structure suitable for expression evaluation / sandbox subprocesses.

    Output shape (per node id):
    {
      "<node_id>": {
        "status": "success|skipped|error|...",
        "main": [
          [ { ...item_json... }, ... ],   # output slot 0
          [ ... ],                        # output slot 1
        ]
      }
    }
    """

    out: dict[str, Any] = {}
    for node_id, entry in (run_data or {}).items():
        if not isinstance(entry, dict):
            continue
        status = entry.get("status")
        data = entry.get("data") or {}
        if not isinstance(data, dict):
            continue
        main = data.get("main")
        if not isinstance(main, list):
            continue

        slots_json: list[list[dict[str, Any]]] = []
        for slot in main:
            if not isinstance(slot, list):
                slots_json.append([])
                continue
            items_json: list[dict[str, Any]] = []
            for it in slot:
                if isinstance(it, ad.flows.FlowItem):
                    items_json.append(it.json)
                elif isinstance(it, dict):
                    ji = it.get("json")
                    if isinstance(ji, dict):
                        # Serialized `FlowItem` from API/browser seed (`{"json": {...}}`).
                        items_json.append(ji)
                    else:
                        # Plain snapshot dict (already item-shaped).
                        items_json.append(it)
            slots_json.append(items_json)

        row: dict[str, Any] = {"status": status, "main": slots_json}
        if "start_time" in entry:
            row["start_time"] = entry["start_time"]
        if "execution_time_ms" in entry:
            row["execution_time_ms"] = entry["execution_time_ms"]
        out[node_id] = row

    return out


def preview_parameter_expression(
    raw: str,
    *,
    run_data: dict[str, Any],
    input_items_json: list[dict[str, Any]],
    preview_item_index: int = 0,
    execution_refs: dict[str, Any] | None = None,
) -> tuple[Any | None, str | None]:
    """
    Evaluate **one** parameter string for interactive UI preview.

    Mirrors ``resolve_parameters`` for a top-level string: if ``raw.strip()`` starts with ``=``,
    evaluates the trailing expression against a synthetic inbound lane built from ``input_items_json``.
    """

    text = raw.strip()
    if not text.startswith("="):
        return (None, None)

    lane_dicts = [dict(x) for x in input_items_json] if input_items_json else [{}]
    idx = max(0, min(preview_item_index, len(lane_dicts) - 1))
    lane: list[ad.flows.FlowItem] = []
    for d in lane_dicts:
        lane.append(ad.flows.FlowItem(json=d, binary={}, meta={}, paired_item=None))
    item = lane[idx]
    input_context = materialize_input_context([lane], input_index=0, item_index=idx)

    try:
        return (
            resolve_parameters(
                text,
                item=item,
                run_data=run_data or {},
                input_context=input_context,
                execution_refs=execution_refs,
            ),
            None,
        )
    except (ExpressionError, TypeError, KeyError, ValueError, ArithmeticError, ZeroDivisionError) as e:
        return (None, str(e))
    except Exception as e:
        return (None, str(e))

