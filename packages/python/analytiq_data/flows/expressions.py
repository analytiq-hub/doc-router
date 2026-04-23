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
    # n8n-ish surface syntax uses $json / $node; map to valid Python identifiers.
    return expr.replace("$json", "_json").replace("$node", "_node")


def _validate_expr_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST_NODES):
            raise ExpressionError(f"Unsupported expression syntax: {type(node).__name__}")
        if isinstance(node, ast.Call):
            # Explicit, even though Call isn't in allowlist.
            raise ExpressionError("Function calls are not allowed in expressions")
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

