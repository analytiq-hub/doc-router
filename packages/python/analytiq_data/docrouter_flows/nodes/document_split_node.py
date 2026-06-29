from __future__ import annotations

"""DocRouter flow node that splits PDF binaries into per-page PDFs."""

import asyncio
from dataclasses import dataclass
from typing import Any

import fitz  # PyMuPDF

import analytiq_data as ad


@dataclass(frozen=True)
class _SplitPageOutput:
    page_idx: int
    page_bytes: bytes
    file_name: str


def _split_pdf_pages_sync(
    pdf_bytes: bytes,
    *,
    start: int,
    slice_stop: int | None,
    step: int,
    base_file_name: str,
) -> tuple[list[_SplitPageOutput], bool]:
    """
    Split a PDF into single-page blobs (CPU-bound; run via ``asyncio.to_thread``).

    Returns ``(pages, is_empty_pdf)``. When ``is_empty_pdf`` is true, ``pages`` is
    empty and the caller should passthrough the original binary ref unchanged.
    """

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        n_pages = doc.page_count
        if n_pages <= 0:
            return [], True

        indices = list(range(n_pages))[start:slice_stop:step]
        if not indices:
            return [], False

        lower = base_file_name.lower()
        stem = base_file_name[: -len(".pdf")] if lower.endswith(".pdf") else base_file_name

        out: list[_SplitPageOutput] = []
        for page_idx in indices:
            single_doc = fitz.open()
            try:
                single_doc.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
                page_bytes = single_doc.tobytes()
            finally:
                single_doc.close()
            out.append(
                _SplitPageOutput(
                    page_idx=page_idx,
                    page_bytes=page_bytes,
                    file_name=f"{stem}_idx_{page_idx}.pdf",
                )
            )
        return out, False
    finally:
        doc.close()


class DocRouterDocumentSplitNode:
    """Split each PDF binary on the item into one output item per selected page.

    Each output item carries a single-page PDF under the same binary property name as
    the source (e.g. input ``pdf`` → output ``pdf`` with one page). Non-PDF binaries
    on the input item are copied onto every fan-out item for that input.
    """

    key = "docrouter.document_split"
    label = "Document Split"
    description = (
        "Splits each input PDF into one output item per page. "
        "Non-PDF binaries are copied to every fan-out item."
    )
    category = "DocRouter"
    palette_group = "docrouter"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    output_port_types = ["main"]
    icon_key = "split"

    # Simple index slicing: 0-based start/stop/step, stop exclusive.
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "title": "Document Split",
        "properties": {
            "start": {
                "type": "integer",
                "minimum": 0,
                "default": 0,
                "description": "First page index (0-based, inclusive).",
            },
            "stop": {
                "type": "integer",
                "minimum": 0,
                "default": 0,
                "description": "Stop page index (0-based, exclusive). 0 = no stop limit (until end).",
            },
            "step": {
                "type": "integer",
                "minimum": 1,
                "default": 1,
                "description": "Step between page indices (must be >= 1).",
            },
        },
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []

        start = params.get("start")
        if start is not None and (not isinstance(start, int) or start < 0):
            errs.append("parameters.start must be a non-negative integer")

        stop = params.get("stop")
        if stop is not None and (not isinstance(stop, int) or stop < 0):
            errs.append("parameters.stop must be a non-negative integer")
        elif (
            isinstance(start, int)
            and isinstance(stop, int)
            and stop > 0
            and stop <= start
        ):
            errs.append("parameters.stop must be greater than parameters.start")

        step = params.get("step")
        if step is not None and (not isinstance(step, int) or step <= 0):
            errs.append("parameters.step must be a positive integer")

        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ):
        params = node.get("parameters") or {}

        start = params.get("start")
        if not isinstance(start, int) or start < 0:
            start = 0

        stop = params.get("stop")
        if not isinstance(stop, int) or stop < 0:
            stop = 0

        step = params.get("step")
        if not isinstance(step, int) or step <= 0:
            step = 1

        slice_stop = None if stop == 0 else stop

        out: list["ad.flows.FlowItem"] = []
        output_item_index = 0

        for item_index, it in enumerate(inputs[0]):
            passthrough_binary: dict[str, ad.flows.BinaryRef] = {}
            pdf_entries: list[tuple[str, ad.flows.BinaryRef]] = []

            for name, ref in (it.binary or {}).items():
                if isinstance(ref, ad.flows.BinaryRef) and ref.mime_type == "application/pdf":
                    pdf_entries.append((name, ref))
                elif isinstance(ref, ad.flows.BinaryRef):
                    passthrough_binary[name] = ref

            fan_out: list["ad.flows.FlowItem"] = []

            for pdf_name, ref in pdf_entries:
                pdf_bytes = await ad.flows.get_binary_stream(ref, context.analytiq_client)
                pages, is_empty_pdf = await asyncio.to_thread(
                    _split_pdf_pages_sync,
                    pdf_bytes,
                    start=start,
                    slice_stop=slice_stop,
                    step=step,
                    base_file_name=ref.file_name or "document.pdf",
                )
                if is_empty_pdf:
                    fan_out.append(
                        ad.flows.FlowItem(
                            json=dict(it.json),
                            binary={**passthrough_binary, pdf_name: ref},
                            meta={
                                **dict(it.meta or {}),
                                "source_node_id": node["id"],
                                "item_index": output_item_index,
                            },
                            paired_item=it.paired_item,
                        )
                    )
                    output_item_index += 1
                    continue

                for page in pages:
                    page_ref = await ad.flows.save_execution_binary_blob(
                        context.analytiq_client,
                        execution_id=context.execution_id,
                        node_id=str(node["id"]),
                        item_index=output_item_index,
                        property_name=pdf_name,
                        blob=page.page_bytes,
                        mime_type="application/pdf",
                        file_name=page.file_name,
                    )
                    fan_out.append(
                        ad.flows.FlowItem(
                            json=dict(it.json),
                            binary={**passthrough_binary, pdf_name: page_ref},
                            meta={
                                **dict(it.meta or {}),
                                "source_node_id": node["id"],
                                "item_index": output_item_index,
                            },
                            paired_item=it.paired_item,
                        )
                    )
                    output_item_index += 1

            if fan_out:
                out.extend(fan_out)
            elif not pdf_entries:
                out.append(
                    ad.flows.FlowItem(
                        json=dict(it.json),
                        binary=dict(it.binary or {}),
                        meta=dict(it.meta or {}),
                        paired_item=it.paired_item,
                    )
                )

        return [out]
