"""
Convert dumped integration node descriptors into DocRouter flow node packages.

Produces `node.manifest.json`, `parameter.schema.json`, optional `http.spec.json`,
and `python_class` stubs under `generated_nodes/` (default).
"""

from .converter import (
    DEFAULT_GENERATED_ROOT,
    convert_jsonl_file,
    emit_node_package,
    validate_packages,
)

__all__ = [
    "DEFAULT_GENERATED_ROOT",
    "convert_jsonl_file",
    "emit_node_package",
    "validate_packages",
]
