from __future__ import annotations

"""DocRouter flow node that runs a configured prompt against flow item context."""

from typing import Any

import analytiq_data as ad

from .. import services as flow_services
from ..document_binary import resolve_pdf_binary_ref
from analytiq_data.flows.item_batch import map_flow_items_batch
from analytiq_data.flows.batch_progress import make_batch_checkpoint_callback
from analytiq_data.flows.node_settings import resolve_node_batch_size


class DocRouterLlmRunNode:
    """Run a prompt against each main input item, optionally with paired OCR text."""

    key = "docrouter.llm_run"
    label = "Run LLM"
    description = "Runs a configured prompt on flow item data with optional OCR context."
    category = "DocRouter"
    palette_group = "docrouter"
    is_trigger = False
    is_merge = True
    batch_execute_inputs: bool = True
    supports_batch_size: bool = True
    min_inputs = 1
    max_inputs = 2
    outputs = 1
    output_labels = ["output"]
    input_port_types = ["main", "docrouter.ocr"]
    icon_key = "llm_run"
    # Keep in sync with ``llm_run.manifest.json``.
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "title": "Run LLM",
        "properties": {
            "prompt_id": {
                "type": "string",
                "title": "Prompt",
                "description": "Prompt to run.",
                "x-ui-widget": "org_prompt_picker",
            },
        },
        "required": ["prompt_id"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        if not isinstance(params.get("prompt_id"), str) or not params["prompt_id"].strip():
            errs.append("parameters.prompt_id is required")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ):
        params = node.get("parameters") or {}
        prompt_id = str(params["prompt_id"]).strip()
        main_items = inputs[0] if inputs else []
        ocr_items = inputs[1] if len(inputs) > 1 else []

        async def _run_item(item_index: int) -> "ad.flows.FlowItem":
            it = main_items[item_index]
            ocr_pages: list[str] | None = None
            if item_index < len(ocr_items):
                ocr_item = ocr_items[item_index]
                raw_pages = ocr_item.json.get("ocr_pages")
                if isinstance(raw_pages, list):
                    ocr_pages = [str(page) for page in raw_pages]

            llm_result = await flow_services.run_flow_llm_run(
                context.analytiq_client,
                context.organization_id,
                prompt_id=prompt_id,
                item_json=dict(it.json),
                ocr_pages=ocr_pages,
            )

            pdf_ref = resolve_pdf_binary_ref(it.binary)
            binary: dict[str, ad.flows.BinaryRef] = {}
            if pdf_ref is not None:
                binary["pdf"] = pdf_ref

            meta = dict(it.meta) if isinstance(it.meta, dict) else {}
            if "item_index" not in meta:
                meta["item_index"] = item_index

            return ad.flows.FlowItem(
                json={"prompt_id": prompt_id, "llm_result": llm_result},
                binary=binary,
                meta=meta,
                paired_item=it.paired_item,
            )

        checkpoint_cb = make_batch_checkpoint_callback(context, node, self)
        item_results = await map_flow_items_batch(
            len(main_items),
            _run_item,
            batch_size=resolve_node_batch_size(node),
            should_stop=lambda: ad.flows.read_stop(context),
            on_items_checkpoint=checkpoint_cb,
            execution_id=context.execution_id,
            node_id=str(node.get("id") or ""),
            node_type=str(node.get("type") or ""),
        )
        out = [item for item in item_results if item is not None]
        return [out]
