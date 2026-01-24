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

async def worker_kb_index(worker_id: str) -> None:
    """
    Worker for KB indexing jobs

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

            msg = await ad.queue.recv_msg(analytiq_client, "kb_index")
            if msg:
                logger.info(f"Worker {worker_id} processing KB index msg: {msg}")
                try:
                    await ad.msg_handlers.process_kb_index_msg(analytiq_client, msg)
                except Exception as e:
                    logger.error(f"Error processing KB index message {msg.get('_id')}: {str(e)}")
                    # Mark message as failed
                    await ad.queue.delete_msg(analytiq_client, "kb_index", str(msg["_id"]), status="failed")
            else:
                await asyncio.sleep(0.2)  # Avoid tight loop when no messages
                
        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)  # Sleep longer on errors to prevent tight loop

async def worker_kb_reconcile(worker_id: str) -> None:
    """
    Worker for periodic KB reconciliation.
    
    Checks KBs with reconcile_enabled=True and runs reconciliation
    if reconcile_interval_seconds has passed since last_reconciled_at.
    """
    ENV = os.getenv("ENV", "dev")
    analytiq_client = ad.common.get_analytiq_client(env=ENV, name=worker_id)
    logger.info(f"Starting KB reconciliation worker {worker_id}")
    
    last_heartbeat = datetime.now(UTC)
    CHECK_INTERVAL_SECS = 10  # Check every 10 seconds for KBs that need reconciliation
    
    while True:
        try:
            now = datetime.now(UTC)
            
            # Log heartbeat every 10 minutes
            if (now - last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL_SECS:
                logger.info(f"KB reconciliation worker {worker_id} heartbeat")
                last_heartbeat = now
            
            # Find KBs with periodic reconciliation enabled
            db = analytiq_client.mongodb_async[ENV]
            kbs = await db.knowledge_bases.find({
                "reconcile_enabled": True,
                "status": {"$in": ["indexing", "active"]}
            }).to_list(length=None)
            
            for kb in kbs:
                kb_id = str(kb["_id"])
                organization_id = kb["organization_id"]
                reconcile_interval = kb.get("reconcile_interval_seconds")
                last_reconciled = kb.get("last_reconciled_at")
                
                if not reconcile_interval:
                    continue
                
                # Check if reconciliation is due
                should_reconcile = False
                if last_reconciled is None:
                    # Never reconciled, do it now
                    should_reconcile = True
                else:
                    # Check if interval has passed
                    # last_reconciled might be a datetime or None
                    if isinstance(last_reconciled, datetime):
                        time_since_reconcile = (now - last_reconciled).total_seconds()
                        if time_since_reconcile >= reconcile_interval:
                            should_reconcile = True
                    else:
                        # Invalid timestamp, reconcile now
                        should_reconcile = True
                
                if should_reconcile:
                    # Try to acquire distributed lock to ensure only one pod reconciles
                    lock_acquired = await ad.kb.reconciliation.acquire_reconciliation_lock(
                        analytiq_client,
                        kb_id,
                        worker_id
                    )
                    
                    if not lock_acquired:
                        # Another pod is already reconciling this KB, skip
                        logger.debug(f"KB {kb_id} is already being reconciled by another pod, skipping")
                        continue
                    
                    try:
                        logger.info(f"Running periodic reconciliation for KB {kb_id} (interval: {reconcile_interval}s)")
                        await ad.kb.reconciliation.reconcile_knowledge_base(
                            analytiq_client,
                            kb_id,
                            organization_id,
                            dry_run=False
                        )
                    except Exception as e:
                        logger.error(f"Error reconciling KB {kb_id}: {e}")
                    finally:
                        # Always release lock, even on error
                        await ad.kb.reconciliation.release_reconciliation_lock(
                            analytiq_client,
                            kb_id,
                            worker_id
                        )
            
            # Sleep before next check
            await asyncio.sleep(CHECK_INTERVAL_SECS)
            
        except Exception as e:
            logger.error(f"KB reconciliation worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(30)  # Sleep longer on errors

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

    # Create N_WORKERS workers of worker_ocr, worker_llm, worker_kb_index, and worker_webhook
    # Only one KB reconciliation worker needed (checks all KBs periodically)
    ocr_workers = [worker_ocr(f"ocr_{i}") for i in range(N_WORKERS)]
    llm_workers = [worker_llm(f"llm_{i}") for i in range(N_WORKERS)]
    kb_index_workers = [worker_kb_index(f"kb_index_{i}") for i in range(N_WORKERS)]
    webhook_workers = [worker_webhook(f"webhook_{i}") for i in range(N_WORKERS)]
    kb_reconcile_worker = [worker_kb_reconcile("kb_reconcile_0")]

    # Run all workers concurrently
    await asyncio.gather(*ocr_workers, *llm_workers, *kb_index_workers, *webhook_workers, *kb_reconcile_worker)

if __name__ == "__main__":
    try:    
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, exiting")
