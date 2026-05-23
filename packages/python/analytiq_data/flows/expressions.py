from __future__ import annotations

"""
Expression / templating helpers for flows.

Only a small subset is implemented today:
- `materialize_node_data(run_data)` exposes prior node outputs by **node id** (``_items`` in expressions).
- Name-keyed ``_node`` uses ``materialize_node_outputs_by_name`` (revision ``nodes`` + ``item_index`` row).
- Expression evaluation and parameter resolution (`resolve_parameters`) for `=`-prefixed strings (Python using injected names such as ``_json``, ``_node`` — no ``$`` aliases).
- A guarded AST whitelist; function calls must be bare names allowlisted in ``_SAFE_CALL_IDS``
  (e.g. ``str(...)``, ``len(...)``)—not arbitrary methods or lambdas.

See `docs/flows.md` §20.3 / §20.4.
"""

import ast
import builtins as _builtins_module
import re
from typing import Any

import analytiq_data as ad


class ExpressionError(ValueError):
    """Raised when an expression fails validation or evaluation."""


# Leading string prefixes that start an f-string (Python 3.12+); we reject these before ``ast.parse``
# so users get a DocRouter-specific hint instead of "f-string: expecting …".
_FSTRING_PREFIX_RE = re.compile(r'(?i)^(?:r[fF]|[fF]r|[fF])(?=[\'"])')


def _reject_fstring_prefix(expr: str) -> None:
    if _FSTRING_PREFIX_RE.match(expr.lstrip()):
        raise ExpressionError(
            "f-strings (f\"…\", rf'…', etc.) are not supported in flow expressions. "
            "Use plain =_json['field'], =_json[\"field\"], or + to build strings — not `{{ }}` templates or f\"…\"."
        )


# Builtins permitted as bare calls: ``str(...)``, ``len(...)``, etc.
# Restricted subset so expressions stay sandboxed alongside ``eval(..., {'__builtins__': {}}, ...)``.
_SAFE_CALL_IDS: frozenset[str] = frozenset(
    {
        "str",
        "repr",
        "len",
        "int",
        "float",
        "bool",
        "round",
        "abs",
        "min",
        "max",
        "sorted",
        "sum",
    }
)

_ALLOWED_AST_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Attribute,
    ast.Subscript,
    ast.Call,
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
    ``start_time`` and ``execution_time_ms`` from the node that **produced** this item
    (``item.meta["source_node_id"]`` → ``run_data[node_id]``).

    The engine sets ``meta.source_node_id`` to the producing node id on every output item.

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


def _safe_builtin_call_env() -> dict[str, Any]:
    """Inject a tiny allowlisted slice of builtins for validated ``Call`` nodes."""

    return {n: getattr(_builtins_module, n) for n in _SAFE_CALL_IDS}


def _validate_expr_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST_NODES):
            raise ExpressionError(f"Unsupported expression syntax: {type(node).__name__}")
        if isinstance(node, ast.Name):
            if node.id.startswith("__"):
                raise ExpressionError("Names starting with '__' are not allowed in expressions")
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ExpressionError("Only direct calls like str(...) are allowed; methods and nested calls targets are forbidden")
            if node.func.id not in _SAFE_CALL_IDS:
                raise ExpressionError(f"Function {node.func.id!r} is not allowed in expressions")
            if node.keywords:
                raise ExpressionError("Keyword arguments are not supported in expression function calls")
            for arg in node.args:
                if isinstance(arg, ast.Starred):
                    raise ExpressionError("Star unpacking is not allowed in expressions")


def _materialize_binary(binary: dict[str, ad.flows.BinaryRef]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (binary or {}).items():
        cell: dict[str, Any] = {
            "mime_type": v.mime_type,
            "file_name": v.file_name,
            # Intentionally omit raw `data` bytes from expression context.
            "data": None,
            "storage_id": v.storage_id,
        }
        if v.file_size is not None:
            cell["file_size"] = v.file_size
        out[k] = cell
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
    Build the ``_input`` dict bound into flow parameter expressions.

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


def _json_from_flow_cell(cell: Any) -> Any:
    if isinstance(cell, ad.flows.FlowItem):
        return cell.json
    if isinstance(cell, dict):
        ji = cell.get("json")
        if isinstance(ji, dict):
            return ji
        return cell
    return {}


def _binary_from_flow_cell(cell: Any) -> dict[str, Any]:
    if isinstance(cell, ad.flows.FlowItem):
        return _materialize_binary(cell.binary or {})
    if isinstance(cell, dict):
        b = cell.get("binary")
        if not isinstance(b, dict):
            return {}
        out: dict[str, Any] = {}
        for k, v in b.items():
            if isinstance(v, ad.flows.BinaryRef):
                br: dict[str, Any] = {
                    "mime_type": v.mime_type,
                    "file_name": v.file_name,
                    "data": None,
                    "storage_id": v.storage_id,
                }
                if v.file_size is not None:
                    br["file_size"] = v.file_size
                out[k] = br
            elif isinstance(v, dict):
                out[k] = {
                    kk: v.get(kk)
                    for kk in ("mime_type", "file_name", "data", "storage_id", "file_size")
                    if kk in v
                }
            else:
                out[k] = v
        return out
    return {}


class _SlotOutputView:
    """Per output slot: ``.json`` / ``.binary`` for the current ``item_index`` row."""

    def __init__(self, lane: list[Any], *, item_index: int | None):
        self._lane = lane
        self._item_index = item_index

    @property
    def json(self) -> Any:
        ii = self._item_index
        if ii is None:
            raise ExpressionError(
                "_node[...].output[...].json is not available when item_index is unset "
                "(batch/merge parameter resolution). Use _input['all'], _items, or avoid row-scoped _node access."
            )
        if ii < 0 or ii >= len(self._lane):
            raise ExpressionError(
                f"_node output row index {ii} is out of range for this slot ({len(self._lane)} items)"
            )
        return _json_from_flow_cell(self._lane[ii])

    @property
    def binary(self) -> dict[str, Any]:
        ii = self._item_index
        if ii is None:
            raise ExpressionError(
                "_node[...].output[...].binary is not available when item_index is unset "
                "(batch/merge parameter resolution). Use _input['all'], _items, or avoid row-scoped _node access."
            )
        if ii < 0 or ii >= len(self._lane):
            raise ExpressionError(
                f"_node output row index {ii} is out of range for this slot ({len(self._lane)} items)"
            )
        return _binary_from_flow_cell(self._lane[ii])


class _OutputSlotsIndexer:
    def __init__(self, slots: list[_SlotOutputView]):
        self._slots = slots

    def __getitem__(self, idx: int) -> _SlotOutputView:
        if idx < 0 or idx >= len(self._slots):
            raise ExpressionError(
                f"_node output slot index {idx} is out of range (this node has {len(self._slots)} output slots in run_data)"
            )
        return self._slots[idx]


class _NamedNodeExprRoot:
    """Name-keyed upstream view: ``.json`` / ``.binary`` ≡ slot 0; ``.output[i]`` for other slots."""

    def __init__(self, slot_views: list[_SlotOutputView]):
        self._slots = slot_views

    @property
    def output(self) -> _OutputSlotsIndexer:
        return _OutputSlotsIndexer(self._slots)

    @property
    def json(self) -> Any:
        return self.output[0].json

    @property
    def binary(self) -> dict[str, Any]:
        return self.output[0].binary


def materialize_node_outputs_by_name(
    revision_nodes: list[dict[str, Any]] | None,
    run_data: dict[str, Any],
    item_index: int | None,
) -> dict[str, Any]:
    """
    Build the ``_node`` mapping for parameter expressions: **display name** → row/slot views.

    Requires ``revision_nodes`` to map node ids to names; ``run_data`` supplies ``data.main`` lanes.
    Row selection uses ``item_index`` (per-item mode); when it is ``None``, accessing ``.json`` / ``.binary``
    on a slot raises ``ExpressionError`` (merge/batch resolution).
    """

    out: dict[str, Any] = {}
    for n in revision_nodes or []:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not nid:
            continue
        entry = run_data.get(nid)
        if not isinstance(entry, dict):
            continue
        display = ad.flows.node_name(n)
        data = entry.get("data") or {}
        main = data.get("main") if isinstance(data, dict) else None
        if not isinstance(main, list):
            main = []
        slot_views = [_SlotOutputView(s if isinstance(s, list) else [], item_index=item_index) for s in main]
        out[display] = _NamedNodeExprRoot(slot_views)
    return out


def eval_expression(
    expr: str,
    *,
    item: ad.flows.FlowItem | None,
    run_data: dict[str, Any],
    input_context: dict[str, Any] | None = None,
    execution_refs: dict[str, Any] | None = None,
    revision_nodes: list[dict[str, Any]] | None = None,
) -> Any:
    """
    Evaluate a single expression string (without leading '=') against the current item and run_data.
    """

    expr = expr.strip()
    rewritten = expr
    _reject_fstring_prefix(rewritten)
    try:
        tree = ast.parse(rewritten, mode="eval")
    except SyntaxError as e:
        if "f-string" in str(e).lower():
            raise ExpressionError(
                "f-string syntax is not supported in flow expressions. "
                "Use =_json['key'] or string concatenation (+), not f\"…{…}\" or `{{ }}` templates."
            ) from e
        raise ExpressionError(f"Invalid expression: {e}") from e
    except Exception as e:
        raise ExpressionError(f"Invalid expression: {e}") from e

    _validate_expr_ast(tree)
    code = compile(tree, "<flow-expr>", "eval")

    refs = execution_refs if execution_refs is not None else {}
    src_start, src_exec_ms = timing_from_items_source_run(item, run_data)
    row_ix: int | None = None
    if input_context is not None:
        raw_ix = input_context.get("item_index")
        if raw_ix is not None:
            row_ix = int(raw_ix)
    env = {
        **_safe_builtin_call_env(),
        "_json": (item.json if item is not None else {}),
        "_binary": (_materialize_binary(item.binary or {}) if item is not None else {}),
        "_node": materialize_node_outputs_by_name(revision_nodes, run_data, row_ix),
        "_execution": dict(refs) if refs else {},
        "_start_time": src_start,
        "_execution_time": src_exec_ms,
        # Multi-lane / current-row context (see ``materialize_input_context``):
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
    revision_nodes: list[dict[str, Any]] | None = None,
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
                revision_nodes=revision_nodes,
            )
        return params
    if isinstance(params, list):
        return [
            resolve_parameters(
                x,
                item=item,
                run_data=run_data,
                input_context=input_context,
                execution_refs=execution_refs,
                revision_nodes=revision_nodes,
            )
            for x in params
        ]
    if isinstance(params, dict):
        return {
            k: resolve_parameters(
                v,
                item=item,
                run_data=run_data,
                input_context=input_context,
                execution_refs=execution_refs,
                revision_nodes=revision_nodes,
            )
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
    revision_nodes: list[dict[str, Any]] | None = None,
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
                revision_nodes=revision_nodes,
            ),
            None,
        )
    except (ExpressionError, TypeError, KeyError, ValueError, ArithmeticError, ZeroDivisionError) as e:
        return (None, str(e))
    except Exception as e:
        return (None, str(e))

