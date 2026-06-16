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
