from __future__ import annotations

"""DocRouter flow node that runs OCR on ``binary.pdf`` and emits ``ocr_pages``."""

import json
from typing import Any

import analytiq_data as ad

from .. import services as flow_services
from ..document_binary import resolve_pdf_binary_ref


class DocRouterOcrNode:
    """Run a selected OCR provider on each input item's PDF binary."""

    key = "docrouter.ocr"
    label = "Run OCR"
    description = "Runs OCR on the input PDF and exposes per-page text for downstream nodes."
    category = "DocRouter"
    palette_group = "docrouter"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    output_port_types = ["docrouter.ocr"]
    icon_key = "ocr"
    # Keep in sync with ``ocr.manifest.json`` (palette / validation source of truth).
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "title": "Run OCR",
        "properties": {
            "ocr_provider": {
                "type": "string",
                "enum": list(flow_services.OCR_PROVIDER_CHOICES),
                "default": "textract",
                "description": "OCR backend to use.",
            },
        },
        "required": ["ocr_provider"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        provider = params.get("ocr_provider")
        if not isinstance(provider, str) or provider not in flow_services.OCR_PROVIDER_CHOICES:
            errs.append("parameters.ocr_provider is required")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ):
        params = node.get("parameters") or {}
        ocr_provider = params.get("ocr_provider") if isinstance(params.get("ocr_provider"), str) else "textract"

        out: list["ad.flows.FlowItem"] = []
        for item_index, it in enumerate(inputs[0]):
            pdf_ref = resolve_pdf_binary_ref(it.binary)
            if pdf_ref is None:
                raise ValueError("Input item missing binary.pdf")
            pdf_bytes = await ad.flows.get_binary_stream(pdf_ref, context.analytiq_client)

            ocr_json, ocr_pages = await flow_services.run_flow_ocr_on_pdf(
                context.analytiq_client,
                context.organization_id,
                pdf_bytes,
                ocr_provider=ocr_provider,
                execution_id=context.execution_id,
            )

            ocr_json_bytes = json.dumps(ocr_json, default=str).encode("utf-8")
            binary: dict[str, ad.flows.BinaryRef] = {
                "pdf": pdf_ref,
                "ocr_json": await ad.flows.save_execution_binary_blob(
                    context.analytiq_client,
                    execution_id=context.execution_id,
                    node_id=str(node["id"]),
                    item_index=item_index,
                    property_name="ocr_json",
                    blob=ocr_json_bytes,
                    mime_type="application/json",
                    file_name="ocr.json",
                ),
            }

            merged_json = dict(it.json)
            merged_json["ocr_provider"] = ocr_provider
            merged_json["ocr_pages"] = ocr_pages

            out.append(
                ad.flows.FlowItem(
                    json=merged_json,
                    binary=binary,
                    meta={"source_node_id": node["id"], "item_index": item_index},
                    paired_item=it.paired_item,
                )
            )
        return [out]
