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


def eval_expression(expr: str, *, item: ad.flows.FlowItem | None, run_data: dict[str, Any]) -> Any:
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

    env = {
        "_json": (item.json if item is not None else {}),
        "_binary": (
            {k: {"mime_type": v.mime_type, "file_name": v.file_name, "data": v.data, "storage_id": v.storage_id}
             for k, v in (item.binary or {}).items()}
            if item is not None
            else {}
        ),
        "_node": materialize_node_data(run_data),
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
) -> Any:
    """
    Recursively resolve parameters, evaluating any string value that starts with '='.
    """

    if isinstance(params, str):
        if params.startswith("="):
            return eval_expression(params[1:], item=item, run_data=run_data)
        return params
    if isinstance(params, list):
        return [resolve_parameters(x, item=item, run_data=run_data) for x in params]
    if isinstance(params, dict):
        return {k: resolve_parameters(v, item=item, run_data=run_data) for k, v in params.items()}
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
                    # Best-effort fallback if something already serialized items earlier.
                    items_json.append(it)
            slots_json.append(items_json)

        out[node_id] = {"status": status, "main": slots_json}

    return out

