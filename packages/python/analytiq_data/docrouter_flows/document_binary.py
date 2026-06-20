from __future__ import annotations

"""Build ``FlowItem.binary`` refs for DocRouter document GridFS keys."""

import mimetypes
from typing import Any

import analytiq_data as ad


def mime_for_storage_key(key: str) -> str:
    kind, _ = mimetypes.guess_type(key)
    return kind or "application/octet-stream"


def document_binary_refs(doc: dict[str, Any]) -> dict[str, ad.flows.BinaryRef]:
    """Map a ``docs`` record to ``pdf`` / ``original`` ``BinaryRef`` entries."""

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
        if orig_key != pdf_key:
            binary["original"] = ad.flows.BinaryRef(
                mime_type=mime_for_storage_key(orig_key),
                file_name=user_display,
                storage_id=f"files:{orig_key}",
            )

    return binary


def resolve_pdf_binary_ref(binary: dict[str, ad.flows.BinaryRef] | None) -> ad.flows.BinaryRef | None:
    """
    Pick one input PDF ``BinaryRef`` for OCR and similar nodes.

    Prefers ``binary["pdf"]`` when present (DocRouter document triggers). Otherwise
    returns the first ``application/pdf`` ref in stable property-name order.

    After ``docrouter.document_split``, the original ``pdf`` key is replaced by
    ``pdf_idx_0``, ``pdf_idx_1``, … — this helper returns ``pdf_idx_0`` only. Use
    ``list_pdf_binary_refs`` when a node must see every page PDF on one item.
    """

    if not binary:
        return None
    pdf_ref = binary.get("pdf")
    if isinstance(pdf_ref, ad.flows.BinaryRef):
        return pdf_ref
    for name in sorted(binary.keys()):
        ref = binary[name]
        if isinstance(ref, ad.flows.BinaryRef) and ref.mime_type == "application/pdf":
            return ref
    return None


def list_pdf_binary_refs(binary: dict[str, ad.flows.BinaryRef] | None) -> list[ad.flows.BinaryRef]:
    """Return all ``application/pdf`` refs on an item, in stable property-name order."""

    if not binary:
        return []
    return [
        binary[name]
        for name in sorted(binary.keys())
        if isinstance(binary[name], ad.flows.BinaryRef)
        and binary[name].mime_type == "application/pdf"
    ]
