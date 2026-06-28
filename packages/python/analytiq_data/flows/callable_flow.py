"""Validation for flows invoked via ``flows.flow_tool``."""

from __future__ import annotations

from typing import Any

import analytiq_data as ad


def validate_callable_flow_revision(nodes: list[dict[str, Any]]) -> None:
    """Require exactly one Sub-flow entry trigger (return value comes from last executed node)."""

    tool_triggers = [n for n in nodes if isinstance(n, dict) and n.get("type") == "flows.trigger.tool"]
    if len(tool_triggers) != 1:
        raise ad.flows.FlowValidationError(
            f"Callable flow must have exactly one Sub-flow entry trigger (found {len(tool_triggers)})"
        )
