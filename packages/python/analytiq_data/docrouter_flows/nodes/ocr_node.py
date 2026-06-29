from __future__ import annotations

"""DocRouter flow node that runs OCR on ``binary.pdf`` and emits ``ocr_pages``."""

import json
from typing import Any

import analytiq_data as ad

from .. import services as flow_services
from ..document_binary import resolve_pdf_binary_ref
from analytiq_data.flows.item_batch import map_flow_items_batch
from analytiq_data.flows.node_settings import resolve_node_batch_size


class DocRouterOcrNode:
    """Run a selected OCR provider on each input item's PDF binary."""

    key = "docrouter.ocr"
    label = "Run OCR"
    description = "Runs OCR on the input PDF and exposes per-page text for downstream nodes."
    category = "DocRouter"
    palette_group = "docrouter"
    is_trigger = False
    is_merge = False
    batch_execute_inputs: bool = True
    supports_batch_size: bool = True
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
            "textract_feature_types": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": list(flow_services.TEXTRACT_FEATURE_CHOICES),
                },
                "default": [],
                "title": "Textract features",
                "description": (
                    "AWS Textract AnalyzeDocument feature types. "
                    "Leave empty for text detection only (plain lines)."
                ),
                "x-ui-widget": "enum_multi_checkbox",
                "x-ui-show-when": {"field": "ocr_provider", "equals": "textract"},
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
        raw_features = params.get("textract_feature_types")
        if raw_features is None:
            return errs
        if not isinstance(raw_features, list):
            errs.append("parameters.textract_feature_types must be an array")
            return errs
        try:
            flow_services.normalize_textract_feature_types(raw_features)
        except ValueError:
            errs.append("parameters.textract_feature_types contains invalid feature types")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ):
        params = node.get("parameters") or {}
        ocr_provider = params.get("ocr_provider") if isinstance(params.get("ocr_provider"), str) else "textract"
        textract_feature_types: list[str] | None = None
        if ocr_provider == "textract":
            raw_features = params.get("textract_feature_types")
            if isinstance(raw_features, list):
                textract_feature_types = flow_services.normalize_textract_feature_types(
                    [x for x in raw_features if isinstance(x, str)]
                )

        input_items = inputs[0]

        async def _run_item(item_index: int) -> "ad.flows.FlowItem | None":
            it = input_items[item_index]
            pdf_ref = resolve_pdf_binary_ref(it.binary)
            if pdf_ref is None:
                return None

            blob_item_index = item_index
            if isinstance(it.meta, dict) and isinstance(it.meta.get("item_index"), int):
                blob_item_index = it.meta["item_index"]

            pdf_bytes = await ad.flows.get_binary_stream(pdf_ref, context.analytiq_client)

            ocr_kwargs: dict[str, Any] = {
                "ocr_provider": ocr_provider,
                "execution_id": context.execution_id,
                "textract_feature_types": textract_feature_types,
            }
            if ocr_provider == "textract":
                ocr_kwargs["textract_priority"] = "high" if item_index == 0 else "low"
            ocr_json, ocr_pages = await flow_services.run_flow_ocr_on_pdf(
                context.analytiq_client,
                context.organization_id,
                pdf_bytes,
                **ocr_kwargs,
            )

            ocr_json_bytes = json.dumps(ocr_json, default=str).encode("utf-8")
            binary: dict[str, ad.flows.BinaryRef] = {
                "pdf": pdf_ref,
                "ocr_json": await ad.flows.save_execution_binary_blob(
                    context.analytiq_client,
                    execution_id=context.execution_id,
                    node_id=str(node["id"]),
                    item_index=blob_item_index,
                    property_name="ocr_json",
                    blob=ocr_json_bytes,
                    mime_type="application/json",
                    file_name="ocr.json",
                ),
            }

            merged_json = dict(it.json)
            merged_json["ocr_provider"] = ocr_provider
            if ocr_provider == "textract":
                merged_json["textract_feature_types"] = textract_feature_types or []
            merged_json["ocr_pages"] = ocr_pages

            return ad.flows.FlowItem(
                json=merged_json,
                binary=binary,
                meta={"source_node_id": node["id"], "item_index": blob_item_index},
                paired_item=it.paired_item,
            )

        item_results = await map_flow_items_batch(
            len(input_items),
            _run_item,
            batch_size=resolve_node_batch_size(node),
            should_stop=lambda: ad.flows.read_stop(context),
            execution_id=context.execution_id,
            node_id=str(node.get("id") or ""),
            node_type=str(node.get("type") or ""),
        )
        out = [item for item in item_results if item is not None]
        return [out]
