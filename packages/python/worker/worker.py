#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
import asyncio
from datetime import datetime, UTC
from datetime import timedelta
import logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import analytiq_data as ad

from worker.slot import WorkerSlot

# Set up the environment variables. This reads the .env file.
ad.common.setup()

logger = logging.getLogger(__name__)

# DocRouter product nodes only at import time; flow builtins register per revision
# (Phase D) when a flow activates or runs — see ensure_builtin_keys_for_revision.
ad.flows.register_docrouter_nodes()

HEARTBEAT_INTERVAL_SECS = 600  # seconds
POLL_MIN_SLEEP = 0.2   # seconds — first idle sleep
POLL_MAX_SLEEP = 5.0   # seconds — cap for exponential backoff

# Shared backoff state per queue type. Safe without locks: single asyncio event loop.
# When any worker on a queue finds a message, all workers on that queue reset to fast polling.
_queue_idle_sleep: dict[str, float] = {}

async def worker_ocr(worker_id: str, slot: WorkerSlot | None = None) -> None:
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
            if slot and slot.should_exit_before_poll():
                logger.info(f"Worker {worker_id} exiting after drain request")
                return

            # Log heartbeat every 10 minutes
            now = datetime.now(UTC)
            if (now - last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL_SECS:
                logger.info(f"Worker {worker_id} heartbeat")
                last_heartbeat = now

            msg = await ad.queue.recv_msg(analytiq_client, "ocr")
            if msg:
                _queue_idle_sleep["ocr"] = POLL_MIN_SLEEP
                logger.info(f"Worker {worker_id} processing OCR msg: {msg}")
                if slot:
                    slot.busy = True
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
                finally:
                    if slot:
                        slot.busy = False
                if slot and slot.should_exit_before_poll():
                    logger.info(f"Worker {worker_id} exiting after drain request")
                    return
            else:
                if slot and slot.should_exit_when_idle():
                    logger.info(f"Worker {worker_id} exiting after drain request")
                    return
                sleep = _queue_idle_sleep.get("ocr", POLL_MIN_SLEEP)
                await asyncio.sleep(sleep)
                _queue_idle_sleep["ocr"] = min(sleep * 2, POLL_MAX_SLEEP)

        except asyncio.CancelledError:
            if slot and slot.busy:
                raise
            logger.info(f"Worker {worker_id} cancelled while idle")
            return
        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)

async def worker_llm(worker_id: str, slot: WorkerSlot | None = None) -> None:
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
            if slot and slot.should_exit_before_poll():
                logger.info(f"Worker {worker_id} exiting after drain request")
                return

            # Log heartbeat every 10 minutes
            now = datetime.now(UTC)
            if (now - last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL_SECS:
                logger.info(f"Worker {worker_id} heartbeat")
                last_heartbeat = now

            msg = await ad.queue.recv_msg(analytiq_client, "llm")
            if msg:
                _queue_idle_sleep["llm"] = POLL_MIN_SLEEP
                logger.info(f"Worker {worker_id} processing LLM msg: {msg}")
                if slot:
                    slot.busy = True
                try:
                    force = msg.get("msg", {}).get("force", False)
                    await ad.msg_handlers.process_llm_msg(analytiq_client, msg, force=force)
                except asyncio.CancelledError:
                    logger.warning(
                        f"Worker {worker_id} cancelled mid-flight on LLM msg {msg.get('_id')}; "
                        f"message will be recovered via visibility timeout"
                    )
                    raise
                finally:
                    if slot:
                        slot.busy = False
                if slot and slot.should_exit_before_poll():
                    logger.info(f"Worker {worker_id} exiting after drain request")
                    return
            else:
                if slot and slot.should_exit_when_idle():
                    logger.info(f"Worker {worker_id} exiting after drain request")
                    return
                sleep = _queue_idle_sleep.get("llm", POLL_MIN_SLEEP)
                await asyncio.sleep(sleep)
                _queue_idle_sleep["llm"] = min(sleep * 2, POLL_MAX_SLEEP)
        except asyncio.CancelledError:
            if slot and slot.busy:
                raise
            logger.info(f"Worker {worker_id} cancelled while idle")
            return
        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)

async def worker_kb_index(worker_id: str, slot: WorkerSlot | None = None) -> None:
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
            if slot and slot.should_exit_before_poll():
                logger.info(f"Worker {worker_id} exiting after drain request")
                return

            # Log heartbeat every 10 minutes
            now = datetime.now(UTC)
            if (now - last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL_SECS:
                logger.info(f"Worker {worker_id} heartbeat")
                last_heartbeat = now

            msg = await ad.queue.recv_msg(analytiq_client, "kb_index")
            if msg:
                _queue_idle_sleep["kb_index"] = POLL_MIN_SLEEP
                logger.info(f"Worker {worker_id} processing KB index msg: {msg}")
                if slot:
                    slot.busy = True
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
                finally:
                    if slot:
                        slot.busy = False
                if slot and slot.should_exit_before_poll():
                    logger.info(f"Worker {worker_id} exiting after drain request")
                    return
            else:
                if slot and slot.should_exit_when_idle():
                    logger.info(f"Worker {worker_id} exiting after drain request")
                    return
                sleep = _queue_idle_sleep.get("kb_index", POLL_MIN_SLEEP)
                await asyncio.sleep(sleep)
                _queue_idle_sleep["kb_index"] = min(sleep * 2, POLL_MAX_SLEEP)

        except asyncio.CancelledError:
            if slot and slot.busy:
                raise
            logger.info(f"Worker {worker_id} cancelled while idle")
            return
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

async def worker_webhook(worker_id: str, slot: WorkerSlot | None = None) -> None:
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
            if slot and slot.should_exit_before_poll():
                logger.info(f"Worker {worker_id} exiting after drain request")
                return

            now = datetime.now(UTC)
            if (now - last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL_SECS:
                logger.info(f"Worker {worker_id} heartbeat")
                last_heartbeat = now

            msg = await ad.queue.recv_msg(analytiq_client, "webhook")
            if msg:
                _queue_idle_sleep["webhook"] = POLL_MIN_SLEEP
                if slot:
                    slot.busy = True
                try:
                    await ad.msg_handlers.process_webhook_msg(analytiq_client, msg)
                except asyncio.CancelledError:
                    logger.warning(f"Worker {worker_id} cancelled mid-flight on webhook msg {msg.get('_id')}, marking failed")
                    await ad.queue.move_to_dlq(analytiq_client, "webhook", str(msg["_id"]), "cancelled mid-flight")
                    raise
                finally:
                    if slot:
                        slot.busy = False
                if slot and slot.should_exit_before_poll():
                    logger.info(f"Worker {worker_id} exiting after drain request")
                    return
                continue

            delivery = await ad.webhooks.claim_next_due_delivery(analytiq_client)
            if delivery:
                _queue_idle_sleep["webhook"] = POLL_MIN_SLEEP
                if slot:
                    slot.busy = True
                try:
                    await ad.webhooks.send_delivery(analytiq_client, delivery)
                except asyncio.CancelledError:
                    logger.warning(f"Worker {worker_id} cancelled mid-flight on webhook delivery {delivery.get('_id')}")
                    raise
                finally:
                    if slot:
                        slot.busy = False
                if slot and slot.should_exit_before_poll():
                    logger.info(f"Worker {worker_id} exiting after drain request")
                    return
                continue

            if slot and slot.should_exit_when_idle():
                logger.info(f"Worker {worker_id} exiting after drain request")
                return
            sleep = _queue_idle_sleep.get("webhook", POLL_MIN_SLEEP)
            await asyncio.sleep(sleep)
            _queue_idle_sleep["webhook"] = min(sleep * 2, POLL_MAX_SLEEP)
        except asyncio.CancelledError:
            if slot and slot.busy:
                raise
            logger.info(f"Worker {worker_id} cancelled while idle")
            return
        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)


async def worker_flow_run(worker_id: str, slot: WorkerSlot | None = None) -> None:
    """
    Worker for `flow_run` queue messages (runs flow executions).
    """
    ENV = os.getenv("ENV", "dev")
    analytiq_client = ad.common.get_analytiq_client(env=ENV, name=worker_id)
    logger.info(f"Starting worker {worker_id}")

    last_heartbeat = datetime.now(UTC)

    while True:
        try:
            if slot and slot.should_exit_before_poll():
                logger.info(f"Worker {worker_id} exiting after drain request")
                return

            now = datetime.now(UTC)
            if (now - last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL_SECS:
                logger.info(f"Worker {worker_id} heartbeat")
                last_heartbeat = now

            msg = await ad.queue.recv_msg(analytiq_client, "flow_run")
            if msg:
                _queue_idle_sleep["flow_run"] = POLL_MIN_SLEEP
                if slot:
                    slot.busy = True
                try:
                    await ad.msg_handlers.process_flow_run_msg(analytiq_client, msg)
                except asyncio.CancelledError:
                    logger.warning(
                        f"Worker {worker_id} cancelled mid-flight on flow_run msg {msg.get('_id')}; "
                        f"message will be recovered via visibility timeout"
                    )
                    raise
                finally:
                    if slot:
                        slot.busy = False
                if slot and slot.should_exit_before_poll():
                    logger.info(f"Worker {worker_id} exiting after drain request")
                    return
            else:
                if slot and slot.should_exit_when_idle():
                    logger.info(f"Worker {worker_id} exiting after drain request")
                    return
                sleep = _queue_idle_sleep.get("flow_run", POLL_MIN_SLEEP)
                await asyncio.sleep(sleep)
                _queue_idle_sleep["flow_run"] = min(sleep * 2, POLL_MAX_SLEEP)
        except asyncio.CancelledError:
            if slot and slot.busy:
                raise
            logger.info(f"Worker {worker_id} cancelled while idle")
            return
        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)


async def worker_flow_cleanup(worker_id: str) -> None:
    """Periodic cleanup of expired flow executions and their flow_blobs."""
    ENV = os.getenv("ENV", "dev")
    analytiq_client = ad.common.get_analytiq_client(env=ENV, name=worker_id)
    retention_days = int(os.getenv("FLOW_EXECUTION_RETENTION_DAYS", "30"))
    logger.info(f"Starting flow cleanup worker {worker_id} (retention={retention_days}d)")

    last_heartbeat = datetime.now(UTC)
    last_stale_check = datetime.now(UTC)
    CHECK_INTERVAL_SECS = 3600  # Run once per hour
    STALE_CHECK_INTERVAL_SECS = 60

    while True:
        try:
            now = datetime.now(UTC)

            if (now - last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL_SECS:
                logger.info(f"Flow cleanup worker {worker_id} heartbeat")
                last_heartbeat = now

            if (now - last_stale_check).total_seconds() >= STALE_CHECK_INTERVAL_SECS:
                try:
                    finalized = await ad.flows.recover_stale_flow_executions(analytiq_client)
                    if finalized:
                        logger.info(f"Flow cleanup: finalized {finalized} stale execution(s)")
                except Exception as e:
                    logger.error(f"Flow cleanup stale execution recovery failed: {e}")
                last_stale_check = now

            cutoff = now - timedelta(days=retention_days)
            db = analytiq_client.mongodb_async[ENV]

            expired_filter = {
                "finished_at": {"$lt": cutoff},
                "status": {"$in": ["success", "error", "cancelled"]},
            }
            cursor = db.flow_executions.find(expired_filter, {"_id": 1})
            processed = 0
            async for execution in cursor:
                processed += 1
                execution_id = str(execution["_id"])
                blobs_deleted = await ad.mongodb.blob.delete_blobs_by_prefix_async(
                    analytiq_client, bucket="flow_blobs", prefix=f"{execution_id}/"
                )
                await db.flow_executions.delete_one({"_id": execution["_id"]})
                logger.info(
                    f"Cleaned up execution {execution_id}: {blobs_deleted} blob(s) deleted"
                )

            if processed:
                logger.info(
                    f"Flow cleanup: processed {processed} expired execution(s) (cutoff={cutoff.date()})"
                )

            await asyncio.sleep(CHECK_INTERVAL_SECS)

        except asyncio.CancelledError:
            logger.warning(f"Flow cleanup worker {worker_id} cancelled")
            raise
        except Exception as e:
            logger.error(f"Flow cleanup worker {worker_id} error: {e}")
            await asyncio.sleep(300)  # Back off 5 min on errors

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
    queues = ["ocr", "llm", "kb_index", "webhook", "flow_run"]
    for queue_name in queues:
        try:
            recovered = await ad.queue.recover_stale_messages(analytiq_client, queue_name)
            logger.info(f"Startup recovery: queue={queue_name} recovered={recovered}")
        except Exception as e:
            logger.error(f"Error recovering queue {queue_name} at startup: {e}")


async def recover_on_worker_startup(analytiq_client) -> None:
    """Recover stale queue messages and orphaned flow executions after a restart."""
    await recover_all_queues(analytiq_client)
    try:
        recovered = await ad.flows.recover_orphaned_running_flow_executions_at_startup(analytiq_client)
        logger.info(f"Startup recovery: orphaned running flow executions recovered={recovered}")
    except Exception as e:
        logger.error(f"Error recovering orphaned running flow executions at startup: {e}")


def start_workers(n_docrouter_workers: int) -> list[asyncio.Task]:
    """
    Deprecated: use ``worker.pool.start_worker_pool`` for hot-resizable per-queue workers.

    Kept for tests that still call this helper with a single count applied to every queue.
    """
    if n_docrouter_workers <= 0:
        logger.info("n_docrouter_workers is %s; not starting worker tasks", n_docrouter_workers)
        return []
    tasks = []
    for i in range(n_docrouter_workers):
        tasks.append(asyncio.create_task(worker_ocr(f"ocr_{i}"), name=f"ocr_{i}"))
        tasks.append(asyncio.create_task(worker_llm(f"llm_{i}"), name=f"llm_{i}"))
        tasks.append(asyncio.create_task(worker_kb_index(f"kb_index_{i}"), name=f"kb_index_{i}"))
        tasks.append(asyncio.create_task(worker_webhook(f"webhook_{i}"), name=f"webhook_{i}"))
        tasks.append(asyncio.create_task(worker_flow_run(f"flow_run_{i}"), name=f"flow_run_{i}"))
    tasks.append(asyncio.create_task(worker_kb_reconcile("kb_reconcile_0"), name="kb_reconcile_0"))
    tasks.append(asyncio.create_task(worker_flow_cleanup("flow_cleanup_0"), name="flow_cleanup_0"))
    logger.info(f"Started {len(tasks)} worker tasks (n_docrouter_workers={n_docrouter_workers})")
    return tasks


async def main():
    # Run startup recovery once with a dedicated client before starting workers
    ENV = os.getenv("ENV", "dev")
    recovery_client = ad.common.get_analytiq_client(env=ENV, name="startup_recovery")
    await recover_on_worker_startup(recovery_client)

    from worker.pool import start_worker_pool

    pool, supervisor = await start_worker_pool()
    try:
        await asyncio.gather(supervisor)
    finally:
        supervisor.cancel()
        await pool.shutdown()
        await asyncio.gather(supervisor, return_exceptions=True)

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
