import logging

import analytiq_data as ad
from analytiq_data.queue.queue import MAX_QUEUE_ATTEMPTS

logger = logging.getLogger(__name__)


async def process_case_llm_msg(analytiq_client, msg, force: bool = False) -> None:
    logger.info(f"Processing case LLM msg: {msg}")
    msg_id = str(msg["_id"])
    attempts = msg.get("attempts", 0)
    payload = msg.get("msg") or {}
    organization_id = payload.get("organization_id")
    case_id = payload.get("case_id")
    prompt_id = payload.get("prompt_id")

    if not organization_id or not case_id or not prompt_id:
        logger.error(f"Invalid case LLM message {msg_id}: missing fields")
        await ad.queue.delete_msg(analytiq_client, "case_llm", msg_id)
        return

    try:
        await ad.case_llm.run_case_llm_from_queue(
            analytiq_client,
            organization_id,
            case_id,
            prompt_id,
        )
        await ad.queue.delete_msg(analytiq_client, "case_llm", msg_id)
    except Exception as e:
        logger.error(
            f"Case LLM failed org={organization_id} case={case_id} prompt={prompt_id}: {e}"
        )
        if attempts >= MAX_QUEUE_ATTEMPTS:
            await ad.queue.move_to_dlq(
                analytiq_client,
                "case_llm",
                msg_id,
                f"Case LLM failed after {attempts} attempts: {e}",
            )
        else:
            await ad.queue.report_last_error(analytiq_client, "case_llm", msg_id, str(e))
            logger.info(
                f"Leaving case LLM message {msg_id} for retry (attempt {attempts} of {MAX_QUEUE_ATTEMPTS})"
            )
