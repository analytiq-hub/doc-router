import asyncio
import openai
import logging
import analytiq_data as ad

logger = logging.getLogger(__name__)

async def process_llm_msg(analytiq_client, msg):
    logger.info(f"Processing LLM msg: {msg}")

    document_id = msg["msg"]["document_id"]
    org_id = None
    
    try:
        doc = await ad.common.doc.get_doc(analytiq_client, document_id)
        if doc:
            org_id = doc.get("organization_id")

        # Update state to LLM processing
        await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_LLM_PROCESSING)

        # Get all the document tags
        tags = await ad.common.doc.get_doc_tag_ids(analytiq_client, document_id)

        # Get all the prompt ids for the tags
        prompt_revids = await ad.common.get_prompt_revision_ids_by_tag_ids(analytiq_client, tags)

        # Add the default prompt id as first prompt
        prompt_revids.insert(0, "default")

        logger.info(f"Running LLM for document {document_id} with prompt id list: {prompt_revids}")

        # Run the LLM for the document for the default prompt
        await ad.llm.run_llm_for_prompt_revids(analytiq_client, document_id, prompt_revids)

        # Update state to LLM completed
        await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED)
        
        logger.info(f"LLM run completed for {document_id}")
    except Exception as e:
        logger.error(f"Error processing LLM msg: {e}")
        
        # Update state to LLM failed
        await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_LLM_FAILED)

        # Optional per-org webhook: error
        try:
            if org_id:
                await ad.webhooks.enqueue_event(
                    analytiq_client,
                    organization_id=org_id,
                    event_type="llm.error",
                    document_id=document_id,
                    error={"stage": "llm", "message": str(e)},
                )
        except Exception:
            pass
        
        # Could add LLM error queue handling here if needed
        
    await ad.queue.delete_msg(analytiq_client, "llm", msg["_id"])