#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
import asyncio
from datetime import datetime, UTC
import logging
# Add the parent directory to the sys path
sys.path.append("..")
import analytiq_data as ad

# Set up the environment variables. This reads the .env file.
ad.common.setup()

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECS = 600  # seconds
POLL_MIN_SLEEP = 0.2   # seconds — first idle sleep
POLL_MAX_SLEEP = 5.0   # seconds — cap for exponential backoff

# Shared backoff state per queue type. Safe without locks: single asyncio event loop.
# When any worker on a queue finds a message, all workers on that queue reset to fast polling.
_queue_idle_sleep: dict[str, float] = {}

async def worker_ocr(worker_id: str) -> None:
    """
    Worker for OCR jobs

    Args:
        worker_id: The worker ID
    """
    # Re-read the environment variables, in case they were changed by unit tests
    ENV = os.getenv("ENV", "dev")

    # Shared Motor pool per process; name is for logging/trace context only
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
                _queue_idle_sleep["ocr"] = POLL_MIN_SLEEP
                logger.info(f"Worker {worker_id} processing OCR msg: {msg}")
                try:
                    force = msg.get("msg", {}).get("force", False)
                    ocr_only = msg.get("msg", {}).get("ocr_only", False)
                    await ad.msg_handlers.process_ocr_msg(analytiq_client, msg, force=force, ocr_only=ocr_only)
                except asyncio.CancelledError:
                    logger.warning(
                        f"Worker {worker_id} cancelled mid-flight on OCR msg {msg.get('_id')}; "
                        f"message will be recovered via visibility timeout"
                    )
                    raise
                except Exception as e:
                    # The OCR handler is responsible for queue state (retry vs DLQ).
                    logger.error(f"Error processing OCR message {msg.get('_id')}: {str(e)}")
            else:
                sleep = _queue_idle_sleep.get("ocr", POLL_MIN_SLEEP)
                await asyncio.sleep(sleep)
                _queue_idle_sleep["ocr"] = min(sleep * 2, POLL_MAX_SLEEP)

        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)

async def worker_llm(worker_id: str) -> None:
    """
    Worker for LLM jobs

    Args:
        worker_id: The worker ID
    """
    # Re-read the environment variables, in case they were changed by unit tests
    ENV = os.getenv("ENV", "dev")

    # Shared Motor pool per process; name is for logging/trace context only
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
                _queue_idle_sleep["llm"] = POLL_MIN_SLEEP
                logger.info(f"Worker {worker_id} processing LLM msg: {msg}")
                try:
                    force = msg.get("msg", {}).get("force", False)
                    await ad.msg_handlers.process_llm_msg(analytiq_client, msg, force=force)
                except asyncio.CancelledError:
                    logger.warning(
                        f"Worker {worker_id} cancelled mid-flight on LLM msg {msg.get('_id')}; "
                        f"message will be recovered via visibility timeout"
                    )
                    raise
            else:
                sleep = _queue_idle_sleep.get("llm", POLL_MIN_SLEEP)
                await asyncio.sleep(sleep)
                _queue_idle_sleep["llm"] = min(sleep * 2, POLL_MAX_SLEEP)
        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)

async def worker_kb_index(worker_id: str) -> None:
    """
    Worker for KB indexing jobs

    Args:
        worker_id: The worker ID
    """
    # Re-read the environment variables, in case they were changed by unit tests
    ENV = os.getenv("ENV", "dev")

    # Shared Motor pool per process; name is for logging/trace context only
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
                _queue_idle_sleep["kb_index"] = POLL_MIN_SLEEP
                logger.info(f"Worker {worker_id} processing KB index msg: {msg}")
                try:
                    await ad.msg_handlers.process_kb_index_msg(analytiq_client, msg)
                except asyncio.CancelledError:
                    logger.warning(
                        f"Worker {worker_id} cancelled mid-flight on KB index msg {msg.get('_id')}; "
                        f"message will be recovered via visibility timeout"
                    )
                    raise
                except Exception as e:
                    logger.error(f"Error processing KB index message {msg.get('_id')}: {str(e)}")
            else:
                sleep = _queue_idle_sleep.get("kb_index", POLL_MIN_SLEEP)
                await asyncio.sleep(sleep)
                _queue_idle_sleep["kb_index"] = min(sleep * 2, POLL_MAX_SLEEP)

        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)

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
            
            logger.debug(f"KB reconciliation worker {worker_id} checking for KBs that need reconciliation")
            
            # Find KBs with periodic reconciliation enabled
            db = analytiq_client.mongodb_async[ENV]
            kbs = await db.knowledge_bases.find({
                "reconcile_enabled": True,
                "status": {"$in": ["indexing", "active"]}
            }).to_list(length=None)
            
            logger.debug(f"Found {len(kbs)} KB(s) with reconcile_enabled=True and active status")
            
            if not kbs:
                logger.debug(f"No KBs found with reconcile_enabled=True and active status")
            
            for kb in kbs:
                kb_id = str(kb["_id"])
                organization_id = kb["organization_id"]
                reconcile_interval = kb.get("reconcile_interval_seconds")
                last_reconciled = kb.get("last_reconciled_at")
                
                if not reconcile_interval:
                    logger.warning(f"KB {kb_id} has reconcile_enabled=True but reconcile_interval_seconds is None or missing. Skipping.")
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
                        # Ensure last_reconciled is timezone-aware (assume UTC if naive)
                        if last_reconciled.tzinfo is None:
                            last_reconciled = last_reconciled.replace(tzinfo=UTC)
                        time_since_reconcile = (now - last_reconciled).total_seconds()
                        if time_since_reconcile >= reconcile_interval:
                            should_reconcile = True
                    else:
                        # Invalid timestamp, reconcile now
                        should_reconcile = True
                
                if should_reconcile:
                    logger.info(f"KB {kb_id} needs reconciliation (last_reconciled: {last_reconciled}, interval: {reconcile_interval}s)")
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
                            organization_id,
                            kb_id=kb_id,
                            dry_run=False
                        )
                    except asyncio.CancelledError:
                        logger.warning(f"Worker {worker_id} cancelled mid-flight during KB {kb_id} reconciliation")
                        raise
                    except Exception as e:
                        logger.error(f"Error reconciling KB {kb_id}: {e}")
                    finally:
                        # Always release lock (runs even on CancelledError before re-raise)
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
                _queue_idle_sleep["webhook"] = POLL_MIN_SLEEP
                try:
                    await ad.msg_handlers.process_webhook_msg(analytiq_client, msg)
                except asyncio.CancelledError:
                    logger.warning(f"Worker {worker_id} cancelled mid-flight on webhook msg {msg.get('_id')}, marking failed")
                    await ad.queue.move_to_dlq(analytiq_client, "webhook", str(msg["_id"]), "cancelled mid-flight")
                    raise
                continue

            delivery = await ad.webhooks.claim_next_due_delivery(analytiq_client)
            if delivery:
                _queue_idle_sleep["webhook"] = POLL_MIN_SLEEP
                try:
                    await ad.webhooks.send_delivery(analytiq_client, delivery)
                except asyncio.CancelledError:
                    logger.warning(f"Worker {worker_id} cancelled mid-flight on webhook delivery {delivery.get('_id')}")
                    raise
                continue

            sleep = _queue_idle_sleep.get("webhook", POLL_MIN_SLEEP)
            await asyncio.sleep(sleep)
            _queue_idle_sleep["webhook"] = min(sleep * 2, POLL_MAX_SLEEP)
        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)

async def recover_all_queues(analytiq_client) -> None:
    """
    Recover stale messages across all queues at worker startup.

    This function is idempotent and safe to call repeatedly. It only touches
    messages that:
    - Are in "processing" status
    - Have processing_started_at older than the visibility timeout

    For each recovered message, ``attempts`` is decremented by 1 (floored at 0)
    so an unfinished claim (e.g. killed worker) does not permanently burn a try.
    """
    queues = ["ocr", "llm", "kb_index", "webhook"]
    for queue_name in queues:
        try:
            recovered = await ad.queue.recover_stale_messages(analytiq_client, queue_name)
            logger.info(f"Startup recovery: queue={queue_name} recovered={recovered}")
        except Exception as e:
            logger.error(f"Error recovering queue {queue_name} at startup: {e}")


def start_workers(n_workers: int) -> list[asyncio.Task]:
    """
    Start all worker coroutines as asyncio Tasks within the running event loop.
    Call from a FastAPI lifespan or any async context. Cancel returned tasks on shutdown.
    """
    tasks = []
    for i in range(n_workers):
        tasks.append(asyncio.create_task(worker_ocr(f"ocr_{i}"),            name=f"ocr_{i}"))
        tasks.append(asyncio.create_task(worker_llm(f"llm_{i}"),            name=f"llm_{i}"))
        tasks.append(asyncio.create_task(worker_kb_index(f"kb_index_{i}"),  name=f"kb_index_{i}"))
        tasks.append(asyncio.create_task(worker_webhook(f"webhook_{i}"),    name=f"webhook_{i}"))
    tasks.append(asyncio.create_task(worker_kb_reconcile("kb_reconcile_0"), name="kb_reconcile_0"))
    logger.info(f"Started {len(tasks)} worker tasks (n_workers={n_workers})")
    return tasks

async def main():
    N_WORKERS = int(os.getenv("N_WORKERS", "1"))

    # Run startup recovery once with a dedicated client before starting workers
    ENV = os.getenv("ENV", "dev")
    recovery_client = ad.common.get_analytiq_client(env=ENV, name="startup_recovery")
    await recover_all_queues(recovery_client)

    tasks = start_workers(N_WORKERS)
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    # Configure logging to ensure it's visible
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger.info("=" * 60)
    logger.info("Starting worker process")
    logger.info("=" * 60)
    try:    
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, exiting")
    except Exception as e:
        logger.error(f"Worker process crashed: {e}", exc_info=True)
        raise
