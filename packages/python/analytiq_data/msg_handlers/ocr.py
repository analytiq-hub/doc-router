import asyncio
import json
import logging
import os
import analytiq_data as ad
import stamina

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

async def process_ocr_msg(analytiq_client, msg, force:bool=False):
    """
    Process an OCR message

    Args:
        analytiq_client : AnalytiqClient
            The analytiq client
        msg : dict
            The OCR message
        force : bool
            Whether to force the processing
    """
    # Implement your job processing logic here
    logger.info(f"Processing OCR msg: {msg}")
    logger.info(f"Force: {force}")

    msg_id = msg["_id"]
    document_id = None
    org_id = None

    try:
        document_id = msg["msg"]["document_id"]

        # Get document info to check if we should skip OCR
        doc = await ad.common.doc.get_doc(analytiq_client, document_id)
        if not doc:
            logger.error(f"Document {document_id} not found. Skipping OCR.")
            return
        org_id = doc.get("organization_id")

        # Check if OCR is supported for this file
        if not ad.common.doc.ocr_supported(doc.get("user_file_name", "")):
            logger.info(f"Skipping OCR processing for structured data file: {document_id} ({doc.get('user_file_name')})")
            # Update state to OCR completed without doing OCR
            await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED)
            # Post a message to the llm job queue
            msg = {"document_id": document_id}
            await ad.queue.send_msg(analytiq_client, "llm", msg=msg)
            return

        # Update state to OCR processing
        await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_OCR_PROCESSING)

        ocr_json = None
        if not force:
            # Check if the OCR text already exists
            ocr_json = await ad.common.get_ocr_json(analytiq_client, document_id)
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
                return

            # Run OCR
            ocr_json = await ad.aws.textract.run_textract(analytiq_client, file["blob"])
            logger.info(f"OCR completed for {document_id}")

            # Save the OCR dictionary
            await ad.common.save_ocr_json(analytiq_client, document_id, ocr_json)
            logger.info(f"OCR list for {document_id} has been saved.")
        
        # Extract the text
        await ad.common.save_ocr_text_from_list(analytiq_client, document_id, ocr_json, force=force)
        logger.info(f"OCR text for {document_id} has been saved.")
        # Update state to OCR completed
        await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED)

        # Post a message to the llm job queue
        msg = {"document_id": document_id}
        await ad.queue.send_msg(analytiq_client, "llm", msg=msg)
        
        # Post a message to the KB indexing queue (OCR-gated indexing)
        kb_msg = {"document_id": document_id}
        await ad.queue.send_msg(analytiq_client, "kb_index", msg=kb_msg)
    
    except Exception as e:
        logger.error(f"Error processing OCR msg: {e}")
        
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

        # Save the message to the ocr_err queue
        await ad.queue.send_msg(analytiq_client, "ocr_err", msg=msg)

    # Delete the message from the ocr queue
    await ad.queue.delete_msg(analytiq_client, "ocr", msg_id)