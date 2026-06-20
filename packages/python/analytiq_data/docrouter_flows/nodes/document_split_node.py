from __future__ import annotations

"""DocRouter flow node that splits PDF binaries into per-page PDFs."""

from typing import Any

import fitz  # PyMuPDF

import analytiq_data as ad


class DocRouterDocumentSplitNode:
    """Split each PDF binary on the item into per-page PDFs.

    Output replaces each input PDF property ``{name}`` with one property per selected
    page: ``{name}_idx_{page}`` (0-based), e.g. ``pdf`` → ``pdf_idx_0``, ``pdf_idx_1``.
    Non-PDF binaries are copied unchanged and keep their original keys/positions.

    Downstream nodes that call ``resolve_pdf_binary_ref`` receive only the first page
    PDF (lowest ``*_idx_*`` key in sorted order). To process every page, iterate
    ``item.binary`` or fan out with a batch/loop node.
    """

    key = "docrouter.document_split"
    label = "Document Split"
    description = (
        "Splits input PDFs into per-page PDFs ({name}_idx_{page} keys). "
        "Non-PDF binaries unchanged. Downstream resolve_pdf_binary_ref sees the first page only."
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

        for item_index, it in enumerate(inputs[0]):
            binary: dict[str, ad.flows.BinaryRef] = {}

            for name, ref in (it.binary or {}).items():
                if not isinstance(ref, ad.flows.BinaryRef) or ref.mime_type != "application/pdf":
                    # Non-PDF binaries are passed through untouched.
                    binary[name] = ref
                    continue

                # Fetch original PDF bytes.
                pdf_bytes = await ad.flows.get_binary_stream(ref, context.analytiq_client)
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                try:
                    n_pages = doc.page_count
                    if n_pages <= 0:
                        # Nothing to split; keep original binary.
                        binary[name] = ref
                        continue

                    indices = list(range(n_pages))[start:slice_stop:step]
                    if not indices:
                        continue

                    base_file_name = ref.file_name or "document.pdf"
                    lower = base_file_name.lower()
                    if lower.endswith(".pdf"):
                        stem = base_file_name[: -len(".pdf")]
                    else:
                        stem = base_file_name

                    for page_idx in indices:
                        single_doc = fitz.open()
                        try:
                            single_doc.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
                            page_bytes = single_doc.tobytes()
                        finally:
                            single_doc.close()

                        new_name = f"{stem}_idx_{page_idx}.pdf"
                        prop_name = f"{name}_idx_{page_idx}"

                        new_ref = await ad.flows.save_execution_binary_blob(
                            context.analytiq_client,
                            execution_id=context.execution_id,
                            node_id=str(node["id"]),
                            item_index=item_index,
                            property_name=prop_name,
                            blob=page_bytes,
                            mime_type="application/pdf",
                            file_name=new_name,
                        )
                        binary[prop_name] = new_ref
                finally:
                    doc.close()

            out.append(
                ad.flows.FlowItem(
                    json=dict(it.json),
                    binary=binary,
                    meta=dict(it.meta or {}),
                    paired_item=it.paired_item,
                )
            )

        return [out]

