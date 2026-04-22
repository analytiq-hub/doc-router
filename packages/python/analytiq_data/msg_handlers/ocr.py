import asyncio
import json
import logging
import os
import analytiq_data as ad
import stamina
from analytiq_data.payments.exceptions import SPUCreditException
from analytiq_data.queue.queue import MAX_QUEUE_ATTEMPTS

logger = logging.getLogger(__name__)


@stamina.retry(on=FileNotFoundError)
async def _ocr_get_file(analytiq_client, file_name: str):
    """
    Get file with retry mechanism for file not found errors.
    This handles race conditions where large files may not be fully committed to GridFS yet.
    """
    file = await ad.common.get_file_async(analytiq_client, file_name)
    if file is None:
        raise FileNotFoundError(f"File {file_name} not found")
    return file

async def process_ocr_msg(analytiq_client, msg, force:bool=False, ocr_only:bool=False):
    """
    Process an OCR message

    Args:
        analytiq_client : AnalytiqClient
            The analytiq client
        msg : dict
            The OCR message
        force : bool
            Whether to force the processing
        ocr_only : bool
            When True, skip enqueueing LLM and KB indexing after OCR completes
    """
    # Implement your job processing logic here
    msg_id = msg["_id"]
    msg_id_str = str(msg_id)
    attempts = msg.get("attempts", 0)
    document_id = None
    org_id = None

    try:
        document_id = msg["msg"]["document_id"]

        # Get document info to check if we should skip OCR
        doc = await ad.common.doc.get_doc(analytiq_client, document_id)
        if not doc:
            logger.error(f"Document {document_id} not found. Skipping OCR.")
            await ad.queue.delete_msg(analytiq_client, "ocr", msg_id_str)
            return
        org_id = doc.get("organization_id")
        logger.info(f"Processing OCR msg: document_id={document_id}, org_id={org_id}, force={force}, ocr_only={ocr_only}")

        # Check if OCR is supported for this file
        if not ad.common.doc.ocr_supported(doc.get("user_file_name", "")):
            logger.info(f"Skipping OCR processing for structured data file: {document_id} ({doc.get('user_file_name')})")
            # Update state to OCR completed without doing OCR
            await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED)
            if not ocr_only:
                # Post a message to the llm job queue
                msg_llm = {"document_id": document_id}
                await ad.queue.send_msg(analytiq_client, "llm", msg=msg_llm)
                # Post a message to the KB indexing queue (for .txt/.md files that can be indexed)
                kb_msg = {"document_id": document_id}
                await ad.queue.send_msg(analytiq_client, "kb_index", msg=kb_msg)
            await ad.queue.delete_msg(analytiq_client, "ocr", msg_id_str)
            return

        # Update state to OCR processing
        await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_OCR_PROCESSING)

        ocr_json = None
        if not force:
            # Check if the OCR text already exists
            ocr_json = await ad.ocr.get_ocr_json(analytiq_client, document_id)
            if ocr_json is not None:
                logger.info(f"OCR list for {document_id} already exists. Skipping OCR.")        
        
        if ocr_json is None:            
            # Get the file
            doc = await ad.common.doc.get_doc(analytiq_client, document_id)
            if not doc or "mongo_file_name" not in doc:
                logger.error(f"Document metadata for {document_id} not found or missing mongo_file_name. Skipping OCR.")
                await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_OCR_FAILED)
                if org_id:
                    await ad.webhooks.enqueue_event(
                        analytiq_client,
                        organization_id=org_id,
                        event_type="document.error",
                        document_id=document_id,
                        error={"stage": "ocr", "message": "missing mongo_file_name"},
                    )
                # For this hard failure, decide between retry and DLQ based on attempts
                if attempts >= MAX_QUEUE_ATTEMPTS:
                    await ad.queue.move_to_dlq(
                        analytiq_client,
                        "ocr",
                        msg_id_str,
                        f"missing mongo_file_name after {attempts} attempts",
                    )
                return

            # Use the PDF file if available, otherwise fallback to original
            pdf_file_name = doc.get("pdf_file_name")
            if pdf_file_name is None:
                logger.error(f"Document metadata for {document_id} not found or missing pdf_file_name. Skipping OCR.")
                await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_OCR_FAILED)
                if org_id:
                    await ad.webhooks.enqueue_event(
                        analytiq_client,
                        organization_id=org_id,
                        event_type="document.error",
                        document_id=document_id,
                        error={"stage": "ocr", "message": "missing pdf_file_name"},
                    )
                if attempts >= MAX_QUEUE_ATTEMPTS:
                    await ad.queue.move_to_dlq(
                        analytiq_client,
                        "ocr",
                        msg_id_str,
                        f"missing pdf_file_name after {attempts} attempts",
                    )
                return

            file = await _ocr_get_file(analytiq_client, pdf_file_name)
            if file is None:
                logger.error(f"File for {document_id} not found. Skipping OCR.")
                await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_OCR_FAILED)
                if org_id:
                    await ad.webhooks.enqueue_event(
                        analytiq_client,
                        organization_id=org_id,
                        event_type="document.error",
                        document_id=document_id,
                        error={"stage": "ocr", "message": "file not found"},
                    )
                if attempts >= MAX_QUEUE_ATTEMPTS:
                    await ad.queue.move_to_dlq(
                        analytiq_client,
                        "ocr",
                        msg_id_str,
                        f"file not found after {attempts} attempts",
                    )
                return

            # Run OCR (mode from org settings: textract, mistral, llm, or pymupdf)
            ocr_cfg = await ad.ocr.fetch_org_ocr_config(analytiq_client, org_id)
            ocr_json = await ad.ocr.run_document_ocr(
                analytiq_client,
                file["blob"],
                org_id=org_id,
                document_id=document_id,
                cfg=ocr_cfg,
            )
            logger.info(f"OCR completed for {document_id}")

            await ad.ocr.save_ocr_json(
                analytiq_client,
                document_id,
                ocr_json,
                metadata={"ocr_type": ocr_cfg.mode},
            )
            logger.info(f"OCR list for {document_id} has been saved.")

        ocr_cfg = await ad.ocr.fetch_org_ocr_config(analytiq_client, org_id)
        # Extract plain text blobs (Textract or pages-markdown)
        await ad.ocr.save_ocr_text_from_json(
            analytiq_client,
            document_id,
            ocr_json,
            force=force,
            org_id=org_id,
            ocr_type=ocr_cfg.mode,
        )
        logger.info(f"OCR text for {document_id} has been saved.")
        # Update state to OCR completed
        await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED)

        if not ocr_only:
            # Post a message to the llm job queue
            msg_llm = {"document_id": document_id, "force": force}
            await ad.queue.send_msg(analytiq_client, "llm", msg=msg_llm)

            # Post a message to the KB indexing queue (OCR-gated indexing)
            kb_msg = {"document_id": document_id}
            await ad.queue.send_msg(analytiq_client, "kb_index", msg=kb_msg)

        # Successful completion: remove message from queue
        await ad.queue.delete_msg(analytiq_client, "ocr", msg_id_str)

    except Exception as e:
        if isinstance(e, SPUCreditException):
            logger.warning(
                f"OCR skipped: insufficient SPU credits document_id={document_id} org_id={org_id} "
                f"required={getattr(e, 'required_spus', None)} available={getattr(e, 'available_spus', None)}"
            )
            if document_id:
                await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_OCR_FAILED)
            try:
                if org_id and document_id:
                    await ad.webhooks.enqueue_event(
                        analytiq_client,
                        organization_id=org_id,
                        event_type="document.error",
                        document_id=document_id,
                        error={
                            "stage": "ocr",
                            "message": "insufficient_spu_credits",
                            "required_spus": getattr(e, "required_spus", None),
                            "available_spus": getattr(e, "available_spus", None),
                        },
                    )
            except Exception:
                pass
            await ad.queue.delete_msg(analytiq_client, "ocr", msg_id_str)
            return

        logger.error(f"Error processing OCR msg: document_id={document_id}, org_id={org_id}, error={e}")
        
        # Update state to OCR failed
        if document_id:
            await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_OCR_FAILED)
        try:
            if org_id and document_id:
                await ad.webhooks.enqueue_event(
                    analytiq_client,
                    organization_id=org_id,
                    event_type="document.error",
                    document_id=document_id,
                    error={"stage": "ocr", "message": str(e)},
                )
        except Exception:
            pass

        # Decide between retry and DLQ based on attempts
        if attempts >= MAX_QUEUE_ATTEMPTS:
            await ad.queue.move_to_dlq(
                analytiq_client,
                "ocr",
                msg_id_str,
                str(e),
            )
        else:
            await ad.queue.report_last_error(
                analytiq_client,
                "ocr",
                msg_id_str,
                str(e),
            )
            logger.info(
                f"Leaving OCR message {msg_id_str} in processing for retry after handler error (document_id={document_id}, org_id={org_id}, attempt {attempts} of {MAX_QUEUE_ATTEMPTS})"
            )