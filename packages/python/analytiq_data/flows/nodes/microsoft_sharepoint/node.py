"""Microsoft SharePoint flow node (type version 1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import analytiq_data as ad

from analytiq_data.flows.integrations.microsoft import (
    MicrosoftGraphApiError,
    format_graph_user_error,
)

from .operations import execute_microsoft_sharepoint_item

_SCHEMA_PATH = Path(__file__).resolve().parent / "parameter.schema.json"


def _load_parameter_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


class FlowsMicrosoftSharePointNode:
    """Consume Microsoft SharePoint via SharePoint REST v2.0 (``microsoftSharePointOAuth2Api``)."""

    key = "flows.microsoft_sharepoint"
    label = "Microsoft SharePoint"
    description = "Consume Microsoft SharePoint API"
    category = "input"
    palette_group = "app"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["main"]
    icon_key = "microsoft_sharepoint"
    type_version = 1
    experimental = True
    parameter_schema = _load_parameter_schema()
    credential_slots = [
        {
            "slot": "microsoftSharePointOAuth2Api",
            "label": "Credential to connect with",
            "required": True,
            "docrouter_binding": "organization_credential_kind:microsoftSharePointOAuth2Api",
        },
    ]

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        slot = inputs[0] if inputs else []
        params = node.get("parameters") if isinstance(node.get("parameters"), dict) else {}
        out: list["ad.flows.FlowItem"] = []
        for i, item in enumerate(slot):
            try:
                result = await execute_microsoft_sharepoint_item(
                    context, node, params, item, item_index=i
                )
                out.append(result)
            except MicrosoftGraphApiError as e:
                msg = format_graph_user_error(e)
                if not node.get("continueOnFail"):
                    raise RuntimeError(msg) from e
                out.append(
                    ad.flows.FlowItem(
                        json={"error": msg},
                        binary=dict(item.binary),
                        meta=dict(item.meta),
                    )
                )
            except Exception as e:
                if not node.get("continueOnFail"):
                    raise
                out.append(
                    ad.flows.FlowItem(
                        json={"error": str(e)},
                        binary=dict(item.binary),
                        meta=dict(item.meta),
                    )
                )
        return [out]
