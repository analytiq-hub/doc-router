from __future__ import annotations

"""DocRouter node implementation for manual document-triggered flows."""

import mimetypes
from typing import Any

import analytiq_data as ad

from .. import services as flow_services


def _mime_for_storage_key(key: str) -> str:
    """Best-effort MIME type from GridFS filename (e.g. ``64f3a1b2.pdf``)."""
    kind, _ = mimetypes.guess_type(key)
    return kind or "application/octet-stream"


class DocRouterManualTriggerNode:
    """Trigger node that emits a single item containing the target document payload."""

    key = "docrouter.trigger.manual"
    label = "Manual trigger (document)"
    description = "Emits the target document as one item."
    category = "DocRouter"
    palette_group = "trigger"
    is_trigger = True
    is_merge = False
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    icon_key = "manual_trigger_document"
    # Triggers have no user-editable parameters; `document_id` comes from the run request / trigger_data.
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": True,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ):
        """Fetch the document and emit it as `json.document` + `json.document_id`."""

        doc_id = context.trigger_data.get("document_id")
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise ValueError("document_id required in trigger_data for docrouter.trigger.manual")
        doc = await flow_services.get_document(context.analytiq_client, context.organization_id, doc_id)

        user_fn = doc.get("user_file_name")
        user_display = user_fn if isinstance(user_fn, str) else None

        binary: dict[str, ad.flows.BinaryRef] = {}
        pdf_key = doc.get("pdf_file_name")
        if isinstance(pdf_key, str) and pdf_key.strip():
            binary["pdf"] = ad.flows.BinaryRef(
                mime_type="application/pdf",
                file_name=user_display or "document.pdf",
                storage_id=f"files:{pdf_key}",
            )

        orig_key = doc.get("mongo_file_name")
        if isinstance(orig_key, str) and orig_key.strip():
            # Avoid duplicate refs when PDF and stored original share the same GridFS key.
            if orig_key != pdf_key:
                binary["original"] = ad.flows.BinaryRef(
                    mime_type=_mime_for_storage_key(orig_key),
                    file_name=user_display,
                    storage_id=f"files:{orig_key}",
                )

        return [
            [
                ad.flows.FlowItem(
                    json={"document": doc, "document_id": doc_id},
                    binary=binary,
                    meta={"source_node_id": node["id"], "item_index": 0},
                    paired_item=None,
                )
            ]
        ]
