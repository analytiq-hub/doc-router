import asyncio
import openai
import logging
from bson import ObjectId
import analytiq_data as ad
from analytiq_data.queue.queue import MAX_QUEUE_ATTEMPTS

logger = logging.getLogger(__name__)

async def process_llm_msg(analytiq_client, msg, force: bool = False):
    logger.info(f"Processing LLM msg: {msg}")

    msg_id = str(msg["_id"])
    attempts = msg.get("attempts", 0)

    document_id = msg["msg"]["document_id"]
    org_id = None
    
    try:
        doc = await ad.common.doc.get_doc(analytiq_client, document_id)
        if doc:
            org_id = doc.get("organization_id")

        # Determine whether the organization has default prompts enabled
        default_prompt_enabled = True
        if org_id:
            try:
                db = ad.common.get_async_db()
                org = await db.organizations.find_one({"_id": ObjectId(org_id)})
                if org is not None:
                    default_prompt_enabled = org.get("default_prompt_enabled", True)
            except Exception as e:
                # If we cannot load the organization, fall back to enabled behavior
                logger.warning(
                    f"Could not load organization {org_id} for default_prompt_enabled; "
                    f"falling back to enabled. Error: {e}"
                )

        # Update state to LLM processing
        await ad.common.doc.update_doc_state(
            analytiq_client,
            document_id,
            ad.common.doc.DOCUMENT_STATE_LLM_PROCESSING,
        )

        # Get all the document tags
        tags = await ad.common.doc.get_doc_tag_ids(analytiq_client, document_id)

        # Get all the prompt ids for the tags
        prompt_revids = await ad.common.get_prompt_revision_ids_by_tag_ids(analytiq_client, tags)

        # Add the default prompt id as first prompt if enabled for this organization
        if default_prompt_enabled:
            prompt_revids.insert(0, "default")

        logger.info(
            f"Running LLM for document {document_id} with prompt id list: {prompt_revids}"
        )

        # Run the LLM for the document for all prompts concurrently
        results = await ad.llm.run_llm_for_prompt_revids(analytiq_client, document_id, prompt_revids, force=force)

        if not results:
            logger.info(f"No LLM prompts executed for document {document_id}; marking as completed")
            await ad.common.doc.update_doc_state(
                analytiq_client,
                document_id,
                ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED,
            )
            await ad.queue.delete_msg(analytiq_client, "llm", msg_id)
            return

        errors = [r for r in results if isinstance(r, Exception)]
        n_errors = len(errors)
        n_total = len(results)

        if n_errors == 0:
            # All prompts succeeded
            await ad.common.doc.update_doc_state(
                analytiq_client,
                document_id,
                ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED,
            )
            logger.info(f"LLM run completed for {document_id} (all {n_total} prompts succeeded)")
            await ad.queue.delete_msg(analytiq_client, "llm", msg_id)
        elif n_errors == n_total:
            # All prompts failed
            error_summary = "; ".join(str(e) for e in errors)
            logger.error(
                f"All LLM prompts failed for {document_id} (attempts={attempts}/{MAX_QUEUE_ATTEMPTS}): {error_summary}"
            )
            await ad.common.doc.update_doc_state(
                analytiq_client,
                document_id,
                ad.common.doc.DOCUMENT_STATE_LLM_FAILED,
            )

            # Optional per-org webhook: error
            try:
                if org_id:
                    await ad.webhooks.enqueue_event(
                        analytiq_client,
                        organization_id=org_id,
                        event_type="llm.error",
                        document_id=document_id,
                        error={"stage": "llm", "message": error_summary},
                    )
            except Exception:
                pass

            # Decide between retry and DLQ based on attempts
            if attempts >= MAX_QUEUE_ATTEMPTS:
                await ad.queue.move_to_dlq(
                    analytiq_client,
                    "llm",
                    msg_id,
                    f"All LLM prompts failed after {attempts} attempts: {error_summary}",
                )
            else:
                logger.info(
                    f"Leaving LLM message {msg_id} in processing for retry (attempt {attempts} of {MAX_QUEUE_ATTEMPTS})"
                )
        else:
            # Partial failure: some prompts succeeded, some failed
            error_summary = "; ".join(str(e) for e in errors)
            logger.warning(
                f"Partial LLM failure for {document_id}: {n_errors}/{n_total} prompts failed: {error_summary}"
            )
            await ad.common.doc.update_doc_state(
                analytiq_client,
                document_id,
                ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED,
            )
            # We intentionally do NOT send an error webhook for partial failures.
            await ad.queue.delete_msg(analytiq_client, "llm", msg_id)

    except Exception as e:
        logger.error(f"Error processing LLM msg: {e}")
        
        # Update state to LLM failed
        await ad.common.doc.update_doc_state(
            analytiq_client,
            document_id,
            ad.common.doc.DOCUMENT_STATE_LLM_FAILED,
        )

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
        
        # Decide between retry and DLQ based on attempts
        if attempts >= MAX_QUEUE_ATTEMPTS:
            await ad.queue.move_to_dlq(
                analytiq_client,
                "llm",
                msg_id,
                f"Unhandled LLM handler error after {attempts} attempts: {e}",
            )
        else:
            logger.info(
                f"Leaving LLM message {msg_id} in processing for retry after handler error "
                f"(attempt {attempts} of {MAX_QUEUE_ATTEMPTS})"
            )