from __future__ import annotations

import ast
import hashlib
import threading
from collections import OrderedDict

from .config import SecurityConfig
from .import_validation import ImportValidationError, validate_import_node
from .security import BLOCKED_ATTRIBUTES, BLOCKED_NAMES


class SecurityValidationError(ValueError):
    pass


class _SecurityValidator(ast.NodeVisitor):
    def __init__(self, config: SecurityConfig) -> None:
        self._config = config

    def visit_Import(self, node: ast.Import) -> None:
        try:
            validate_import_node(node, self._config)
        except ImportValidationError as e:
            raise SecurityValidationError(str(e)) from e
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        try:
            validate_import_node(node, self._config)
        except ImportValidationError as e:
            raise SecurityValidationError(str(e)) from e
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in BLOCKED_NAMES:
            raise SecurityValidationError(f"Use of blocked name '{node.id}' is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in BLOCKED_ATTRIBUTES:
            raise SecurityValidationError(
                f"Access to blocked attribute '{node.attr}' is not allowed"
            )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.value, ast.Name) and node.value.id == "__builtins__":
            raise SecurityValidationError("__builtins__ subscript access is not allowed")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            if not node.args or not isinstance(node.args[0], ast.Constant):
                raise SecurityValidationError("Dynamic __import__ is not allowed")
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                self._check_format_value(value.value)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        for case in node.cases:
            for pattern in self._walk_match_patterns(case.pattern):
                if isinstance(pattern, ast.MatchAs) and pattern.name in BLOCKED_NAMES:
                    raise SecurityValidationError(
                        f"Match pattern may not bind blocked name '{pattern.name}'"
                    )
                if isinstance(pattern, ast.MatchStar) and pattern.name in BLOCKED_NAMES:
                    raise SecurityValidationError(
                        f"Match pattern may not bind blocked name '{pattern.name}'"
                    )
        self.generic_visit(node)

    def _check_format_value(self, node: ast.AST) -> None:
        if isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            raise SecurityValidationError(
                f"Format string may not reference blocked name '{node.id}'"
            )
        if isinstance(node, ast.Attribute) and node.attr in BLOCKED_ATTRIBUTES:
            raise SecurityValidationError(
                f"Format string may not reference blocked attribute '{node.attr}'"
            )

    def _walk_match_patterns(self, pattern: ast.AST):
        yield pattern
        if isinstance(pattern, ast.MatchSequence):
            for p in pattern.patterns:
                yield from self._walk_match_patterns(p)
        elif isinstance(pattern, ast.MatchMapping):
            for p in pattern.keys:
                if isinstance(p, ast.MatchValue):
                    yield from self._walk_match_patterns(p.value)
        elif isinstance(pattern, ast.MatchClass):
            for p in pattern.patterns:
                yield from self._walk_match_patterns(p)
        elif isinstance(pattern, ast.MatchOr):
            for p in pattern.patterns:
                yield from self._walk_match_patterns(p)


_CACHE: OrderedDict[str, None] = OrderedDict()
_CACHE_MAX = 500
_CACHE_LOCK = threading.Lock()


class TaskAnalyzer:
    def validate(self, code: str, config: SecurityConfig) -> None:
        key = hashlib.sha256((code + config.cache_key()).encode("utf-8")).hexdigest()
        with _CACHE_LOCK:
            if key in _CACHE:
                return
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                raise SecurityValidationError(f"Syntax error: {e}") from e
            _SecurityValidator(config).visit(tree)
            _CACHE[key] = None
            if len(_CACHE) > _CACHE_MAX:
                _CACHE.popitem(last=False)
