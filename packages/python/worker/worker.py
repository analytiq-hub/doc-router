#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, UTC
import logging
# Add the parent directory to the sys path
sys.path.append("..")
import analytiq_data as ad

# Set up the environment variables. This reads the .env file.
ad.common.setup()

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECS = 600  # seconds

async def worker_ocr(worker_id: str) -> None:
    """
    Worker for OCR jobs

    Args:
        worker_id: The worker ID
    """
    # Re-read the environment variables, in case they were changed by unit tests
    ENV = os.getenv("ENV", "dev")

    # Create a separate client instance for each worker
    analytiq_client = ad.common.get_analytiq_client(env=ENV, name=worker_id)
    logger.info(f"Starting worker {worker_id}")

    last_heartbeat = datetime.now(UTC)

    while True:
        try:
            # Log heartbeat every 10 minutes
            now = datetime.now(UTC)
            if (now - last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL_SECS: 
                logger.info(f"Worker {worker_id} heartbeat")
                last_heartbeat = now

            msg = await ad.queue.recv_msg(analytiq_client, "ocr")
            if msg:
                logger.info(f"Worker {worker_id} processing OCR msg: {msg}")
                try:
                    await ad.msg_handlers.process_ocr_msg(analytiq_client, msg)
                except Exception as e:
                    logger.error(f"Error processing OCR message {msg.get('_id')}: {str(e)}")
                    # Mark message as failed
                    await ad.queue.delete_msg(analytiq_client, "ocr", str(msg["_id"]), status="failed")
            else:
                await asyncio.sleep(0.2)  # Avoid tight loop when no messages
                
        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)  # Sleep longer on errors to prevent tight loop

async def worker_llm(worker_id: str) -> None:
    """
    Worker for LLM jobs

    Args:
        worker_id: The worker ID
    """
    # Re-read the environment variables, in case they were changed by unit tests
    ENV = os.getenv("ENV", "dev")

    # Create a separate client instance for each worker
    analytiq_client = ad.common.get_analytiq_client(env=ENV, name=worker_id)
    logger.info(f"Starting worker {worker_id}")

    last_heartbeat = datetime.now(UTC)

    while True:
        try:
            # Log heartbeat every 10 minutes
            now = datetime.now(UTC)
            if (now - last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL_SECS: 
                logger.info(f"Worker {worker_id} heartbeat")
                last_heartbeat = now

            msg = await ad.queue.recv_msg(analytiq_client, "llm")
            if msg:
                logger.info(f"Worker {worker_id} processing LLM msg: {msg}")
                await ad.msg_handlers.process_llm_msg(analytiq_client, msg)
            else:
                await asyncio.sleep(0.2)  # Avoid tight loop
        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)  # Sleep longer on errors to prevent tight loop

async def worker_webhook(worker_id: str) -> None:
    """
    Worker for outbound webhook deliveries.

    - Consumes `queues.webhook` for immediate triggers
    - Also scans for due deliveries in `webhook_deliveries` to handle retries even if no queue message exists
    """
    ENV = os.getenv("ENV", "dev")
    analytiq_client = ad.common.get_analytiq_client(env=ENV, name=worker_id)
    logger.info(f"Starting worker {worker_id}")

    last_heartbeat = datetime.now(UTC)

    while True:
        try:
            now = datetime.now(UTC)
            if (now - last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL_SECS:
                logger.info(f"Worker {worker_id} heartbeat")
                last_heartbeat = now

            msg = await ad.queue.recv_msg(analytiq_client, "webhook")
            if msg:
                await ad.msg_handlers.process_webhook_msg(analytiq_client, msg)
                continue

            # No queue message: try processing a due retry directly from webhook_deliveries
            delivery = await ad.webhooks.claim_next_due_delivery(analytiq_client)
            if delivery:
                await ad.webhooks.send_delivery(analytiq_client, delivery)
                continue

            await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)

async def main():
    # Re-read the environment variables, in case they were changed by unit tests
    N_WORKERS = int(os.getenv("N_WORKERS", "1"))

    # Create N_WORKERS workers of worker_ocr and worker_llm
    ocr_workers = [worker_ocr(f"ocr_{i}") for i in range(N_WORKERS)]
    llm_workers = [worker_llm(f"llm_{i}") for i in range(N_WORKERS)]
    webhook_workers = [worker_webhook(f"webhook_{i}") for i in range(N_WORKERS)]

    # Run all workers concurrently
    await asyncio.gather(*ocr_workers, *llm_workers, *webhook_workers)

if __name__ == "__main__":
    try:    
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, exiting")
