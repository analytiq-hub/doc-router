from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Any

from bson import ObjectId

import analytiq_data as ad


logger = logging.getLogger(__name__)


class FlowServicesImpl:
    def __init__(self, analytiq_client):
        self.analytiq_client = analytiq_client

    async def get_document(self, org_id: str, doc_id: str) -> dict:
        doc = await ad.common.doc.get_doc(self.analytiq_client, doc_id)
        if not doc:
            raise ValueError(f"Document not found: {doc_id}")
        if doc.get("organization_id") != org_id:
            raise ValueError("Document does not belong to organization")
        doc["_id"] = str(doc["_id"])
        return doc

    async def run_ocr(self, org_id: str, doc_id: str) -> dict:
        # If OCR already exists, return it.
        existing = await ad.ocr.get_ocr_json(self.analytiq_client, doc_id)
        if existing is not None:
            return {"document_id": doc_id, "ocr": "exists"}

        doc = await self.get_document(org_id, doc_id)
        pdf_file_name = doc.get("pdf_file_name")
        if not pdf_file_name:
            raise ValueError("Document missing pdf_file_name")

        pdf_bytes = await ad.common.get_file_async(self.analytiq_client, pdf_file_name)
        if pdf_bytes is None:
            raise ValueError("PDF blob not found")

        cfg = await ad.ocr.ocr_config.fetch_org_ocr_config(self.analytiq_client, org_id)
        payload = await ad.ocr.ocr_runners.run_document_ocr(
            self.analytiq_client,
            pdf_bytes,
            org_id=org_id,
            document_id=doc_id,
            cfg=cfg,
        )

        metadata: dict[str, Any] = {"org_id": org_id, "ocr_type": cfg.mode}
        await ad.ocr.save_ocr_json(self.analytiq_client, doc_id, payload, metadata=metadata, encoding="json")
        await ad.ocr.save_ocr_text_from_json(
            self.analytiq_client,
            doc_id,
            payload,
            metadata=metadata,
            force=True,
            org_id=org_id,
            ocr_type=cfg.mode if cfg.mode != "mistral_vertex" else "mistral",
        )
        await ad.common.doc.update_doc_state(
            self.analytiq_client, doc_id, ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED
        )
        return {"document_id": doc_id, "ocr": "completed", "mode": cfg.mode}

    async def run_llm_extract(self, org_id: str, doc_id: str, prompt_id: str, schema_id: str) -> dict:
        db = ad.common.get_async_db(self.analytiq_client)
        # Resolve latest prompt revision by prompt_id.
        pr = await db.prompt_revisions.find_one({"prompt_id": prompt_id}, sort=[("prompt_version", -1)])
        if not pr:
            raise ValueError(f"Prompt not found: {prompt_id}")
        prompt_revid = str(pr["_id"])

        # Best-effort schema override: if provided, ensure schema exists (latest).
        if schema_id:
            sr = await db.schema_revisions.find_one({"schema_id": schema_id}, sort=[("schema_version", -1)])
            if not sr:
                raise ValueError(f"Schema not found: {schema_id}")

        # Reuse existing LLM runner; return its raw output.
        results = await ad.llm.run_llm_for_prompt_revids(self.analytiq_client, doc_id, [prompt_revid], force=True)
        if not results:
            return {"document_id": doc_id, "prompt_id": prompt_id, "result": None}
        r0 = results[0]
        if isinstance(r0, Exception):
            raise r0
        return {"document_id": doc_id, "prompt_id": prompt_id, "result": r0}

    async def set_tags(self, org_id: str, doc_id: str, tags: list[str]) -> None:
        db = ad.common.get_async_db(self.analytiq_client)
        # Validate tags exist for org.
        if tags:
            existing = await db.tags.find(
                {"_id": {"$in": [ObjectId(t) for t in tags]}, "organization_id": org_id}
            ).to_list(length=None)
            if len(existing) != len(set(tags)):
                raise ValueError("One or more tag ids are invalid for organization")

        await db.docs.update_one(
            {"_id": ObjectId(doc_id), "organization_id": org_id},
            {"$set": {"tag_ids": list(tags), "updated_at": datetime.now(UTC)}},
        )

    async def send_webhook(self, url: str, payload: dict, headers: dict) -> dict:
        # Reuse outbound webhook infra by enqueuing an event-like delivery.
        # For v1 flows, a direct HTTP call is acceptable.
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers or {})
            return {"status_code": resp.status_code, "body": resp.text}

    async def get_runtime_state(self, flow_id: str, node_id: str) -> dict:
        db = ad.common.get_async_db(self.analytiq_client)
        doc = await db.flow_runtime_state.find_one({"flow_id": flow_id, "node_id": node_id})
        return (doc or {}).get("data") or {}

    async def set_runtime_state(self, flow_id: str, node_id: str, data: dict) -> None:
        db = ad.common.get_async_db(self.analytiq_client)
        await db.flow_runtime_state.update_one(
            {"flow_id": flow_id, "node_id": node_id},
            {"$set": {"data": data, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )

