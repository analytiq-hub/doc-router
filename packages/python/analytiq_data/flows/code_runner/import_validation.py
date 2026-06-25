from __future__ import annotations

import ast

from .config import SecurityConfig


class ImportValidationError(ValueError):
    pass


def validate_import_node(node: ast.Import | ast.ImportFrom, config: SecurityConfig) -> None:
    if isinstance(node, ast.ImportFrom):
        if node.level and node.level > 0:
            raise ImportValidationError("Relative imports are not allowed")
        module = node.module or ""
        if module:
            top = module.split(".")[0]
            if not config.is_module_allowed(top):
                raise ImportValidationError(f"Import of module '{top}' is not allowed")
        for alias in node.names:
            if alias.name == "*":
                raise ImportValidationError("Wildcard imports are not allowed")
            top = alias.name.split(".")[0]
            if not config.is_module_allowed(top):
                raise ImportValidationError(f"Import of module '{top}' is not allowed")
        return

    for alias in node.names:
        top = alias.name.split(".")[0]
        if not config.is_module_allowed(top):
            raise ImportValidationError(f"Import of module '{top}' is not allowed")
