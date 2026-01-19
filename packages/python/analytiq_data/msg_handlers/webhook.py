import logging

import analytiq_data as ad

logger = logging.getLogger(__name__)


async def process_webhook_msg(analytiq_client, msg):
    """
    Process a webhook queue message. The message body is expected to contain:
      msg["msg"]["delivery_id"] (string ObjectId)
    """
    logger.info(f"Processing webhook msg: {msg}")
    delivery_id = None
    try:
        delivery_id = msg.get("msg", {}).get("delivery_id")
        if not delivery_id:
            logger.error("Webhook msg missing delivery_id")
            return

        delivery = await ad.webhooks.claim_delivery_by_id(analytiq_client, delivery_id)
        if not delivery:
            # Not due yet or already handled by another worker.
            return

        await ad.webhooks.send_delivery(analytiq_client, delivery)
    except Exception as e:
        logger.error(f"Error processing webhook msg (delivery_id={delivery_id}): {e}")
    finally:
        # Always complete the queue message; delivery retries are driven by webhook_deliveries.
        try:
            await ad.queue.delete_msg(analytiq_client, "webhook", str(msg["_id"]), status="completed")
        except Exception:
            pass

