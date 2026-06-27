from __future__ import annotations

"""Tool Code node — sandboxed Python exposed as an LLM tool (`flows.tool_code`)."""

import json
import re
from typing import Any

import analytiq_data as ad

_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class FlowsToolCodeNode:
    key = "flows.tool_code"
    label = "Tool Code"
    description = "Exposes sandboxed Python as a named LLM tool."
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
    icon_key = "code"
    type_version = 1
    experimental = True
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "minLength": 1,
                "description": "Function name for the LLM (lowercase, underscores).",
                "x-ui-group": "Tool",
            },
            "tool_description": {
                "type": "string",
                "minLength": 1,
                "description": "Description shown to the model.",
                "x-ui-widget": "textarea",
                "x-ui-group": "Tool",
            },
            "parameters_schema": {
                "type": "object",
                "description": "JSON Schema for tool arguments.",
                "x-ui-widget": "json",
                "x-ui-group": "Tool",
                "default": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            },
            "python_code": {
                "type": "string",
                "minLength": 1,
                "default": "def run(params, context):\n  return {\"echo\": params}\n",
                "description": "Must define def run(params: dict, context: dict) -> dict.",
                "x-ui-widget": "code",
                "x-ui-group": "Code",
            },
            "timeout_seconds": {
                "type": "number",
                "default": 30,
                "minimum": 0.0001,
                "maximum": 120,
                "x-ui-group": "Options",
            },
        },
        "required": ["tool_name", "tool_description", "parameters_schema", "python_code"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        name = str(params.get("tool_name") or "").strip()
        if not name or not _TOOL_NAME_RE.match(name):
            errs.append("parameters.tool_name must match ^[a-z][a-z0-9_]{0,63}$")
        if not str(params.get("tool_description") or "").strip():
            errs.append("parameters.tool_description is required")
        schema = params.get("parameters_schema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            errs.append("parameters.parameters_schema must be a JSON Schema object with type object")
        if not isinstance(params.get("python_code"), str) or not params["python_code"].strip():
            errs.append("parameters.python_code must be a non-empty string")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        """Tool providers are dispatched on demand; not executed on the main DAG."""

        return [[]]
