"""Static checks on Code / Tool Code source, in the worker before it reaches the sandbox.

These checks are a **second layer**: they block the common ways out of a Python-level namespace
(dunder names, frame / generator / coroutine / traceback attributes, imports outside the
allow-list), but a Python-level block list is not a security boundary. The boundary is the sandbox
the code runs in (``wasi.py``).
"""

from __future__ import annotations

import ast

from .config import allowed_modules

BLOCKED_NAMES: frozenset[str] = frozenset(
    {
        "__builtins__",
        "__loader__",
        "__spec__",
        "__globals__",
        "__code__",
        "__closure__",
        "__func__",
        "__self__",
        "__class__",
        "__bases__",
        "__mro__",
        "__subclasses__",
        "__import__",
        "__dict__",
        "__weakref__",
        "__annotations__",
        "__module__",
        "__qualname__",
        "__wrapped__",
        "__traceback__",
        "__context__",
        "__cause__",
        "__frame__",
        "__tb__",
    }
)

BLOCKED_ATTRIBUTES: frozenset[str] = BLOCKED_NAMES | frozenset(
    {
        # Frames, and the objects that lead to them: a running generator's ``gi_frame.f_back``
        # walks up to the runner's own frames and globals.
        "gi_frame",
        "gi_code",
        "gi_yieldfrom",
        "gi_running",
        "cr_frame",
        "cr_code",
        "cr_await",
        "cr_origin",
        "ag_frame",
        "ag_code",
        "ag_await",
        "f_back",
        "f_globals",
        "f_locals",
        "f_builtins",
        "f_code",
        "f_trace",
        "f_lineno",
        "tb_frame",
        "tb_next",
        "tb_lasti",
        "co_consts",
        "co_code",
        "co_names",
        "__reduce__",
        "__reduce_ex__",
        "__getattribute__",
        "__setattr__",
        "__delattr__",
        "__init_subclass__",
        "__set_name__",
        "__getstate__",
        "__setstate__",
    }
)


class CodeCheckError(ValueError):
    """The code was refused before running (syntax, an import, a name or an attribute)."""


class _Validator(ast.NodeVisitor):
    def __init__(self, allowed: set[str]) -> None:
        self._allowed = allowed
        self._any_module = "*" in allowed

    def _module(self, name: str) -> None:
        top = name.split(".")[0]
        if not self._any_module and top not in self._allowed:
            raise CodeCheckError(f"Import of module '{top}' is not allowed")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._module(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            raise CodeCheckError("Relative imports are not allowed")
        if node.module:
            self._module(node.module)
        for alias in node.names:
            if alias.name == "*":
                raise CodeCheckError("Wildcard imports are not allowed")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in BLOCKED_NAMES:
            raise CodeCheckError(f"Use of blocked name '{node.id}' is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in BLOCKED_ATTRIBUTES:
            raise CodeCheckError(f"Access to blocked attribute '{node.attr}' is not allowed")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            raise CodeCheckError("__import__ is not allowed: use an import statement")
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                inner = value.value
                if isinstance(inner, ast.Name) and inner.id in BLOCKED_NAMES:
                    raise CodeCheckError(f"Format string may not reference '{inner.id}'")
                if isinstance(inner, ast.Attribute) and inner.attr in BLOCKED_ATTRIBUTES:
                    raise CodeCheckError(f"Format string may not reference '{inner.attr}'")
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name in BLOCKED_NAMES:
            raise CodeCheckError(f"Match pattern may not bind blocked name '{node.name}'")
        self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name in BLOCKED_NAMES:
            raise CodeCheckError(f"Match pattern may not bind blocked name '{node.name}'")
        self.generic_visit(node)


def check_code(code: str, modules: list[str] | None = None) -> None:
    """Raise ``CodeCheckError`` for a syntax error or a refused import, name or attribute."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise CodeCheckError(f"Syntax error: {e}") from None
    _Validator(set(modules if modules is not None else allowed_modules())).visit(tree)
