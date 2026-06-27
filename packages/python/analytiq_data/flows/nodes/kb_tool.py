from __future__ import annotations

"""Knowledge Base Tool node — hybrid KB search as an LLM tool."""

import re
from typing import Any

import analytiq_data as ad

_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class FlowsKbToolNode:
    key = "flows.kb_tool"
    label = "Knowledge Base Tool"
    description = "Exposes knowledge-base search as a named LLM tool."
    category = "AI"
    palette_group = "ai"
    tool_provider = True
    is_trigger = False
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["tool"]
    output_port_types = ["flows.tool"]
    icon_key = "knowledge_base"
    type_version = 1
    experimental = True
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "knowledge_base_id": {
                "type": "string",
                "description": "Knowledge base to search.",
                "x-ui-widget": "knowledge_base_picker",
                "x-ui-group": "Knowledge base",
            },
            "tool_name": {
                "type": "string",
                "description": "LLM function name.",
                "x-ui-group": "Tool",
            },
            "tool_description": {
                "type": "string",
                "description": "Description shown to the model.",
                "x-ui-widget": "textarea",
                "x-ui-group": "Tool",
            },
            "default_top_k": {
                "type": "integer",
                "default": 5,
                "minimum": 1,
                "maximum": 20,
                "x-ui-group": "Options",
            },
            "default_coalesce_neighbors": {
                "type": "integer",
                "x-ui-group": "Options",
            },
        },
        "required": ["knowledge_base_id", "tool_name", "tool_description"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        if not str(params.get("knowledge_base_id") or "").strip():
            errs.append("parameters.knowledge_base_id is required")
        name = str(params.get("tool_name") or "").strip()
        if not name or not _TOOL_NAME_RE.match(name):
            errs.append("parameters.tool_name must match ^[a-z][a-z0-9_]{0,63}$")
        if not str(params.get("tool_description") or "").strip():
            errs.append("parameters.tool_description is required")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        return [[]]
