import asyncio
import openai
import logging
import analytiq_data as ad

logger = logging.getLogger(__name__)

async def process_llm_msg(analytiq_client, msg):
    logger.info(f"Processing LLM msg: {msg}")

    document_id = msg["msg"]["document_id"]
    
    try:
        # Update state to LLM processing
        await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_LLM_PROCESSING)

        # Get all the document tags
        tags = await ad.common.doc.get_doc_tag_ids(analytiq_client, document_id)

        # Get all the prompt ids for the tags
        prompt_rev_ids = await ad.common.get_prompt_revision_ids_by_tag_ids(analytiq_client, tags)

        # Add the default prompt id as first prompt
        prompt_rev_ids.insert(0, "default")

        logger.info(f"Running LLM for document {document_id} with prompt id list: {prompt_rev_ids}")

        # Run the LLM for the document for the default prompt
        await ad.llm.run_llm_for_prompt_rev_ids(analytiq_client, document_id, prompt_rev_ids)

        # Update state to LLM completed
        await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED)
        
        logger.info(f"LLM run completed for {document_id}")
    except Exception as e:
        logger.error(f"Error processing LLM msg: {e}")
        
        # Update state to LLM failed
        await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_LLM_FAILED)
        
        # Could add LLM error queue handling here if needed
        
    await ad.queue.delete_msg(analytiq_client, "llm", msg["_id"])