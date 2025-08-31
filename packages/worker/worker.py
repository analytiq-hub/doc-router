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

# Environment variables
ENV = os.getenv("ENV", "dev")
N_WORKERS = int(os.getenv("N_WORKERS", "1"))  # Convert to int with default value of 1

logger = logging.getLogger(__name__)
logger.info(f"ENV: {ENV}")
logger.info(f"N_WORKERS: {N_WORKERS}")

HEARTBEAT_INTERVAL_SECS = 600  # seconds

async def worker_ocr(worker_id: str) -> None:
    """
    Worker for OCR jobs

    Args:
        worker_id: The worker ID
    """
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

async def worker_lambda(worker_id: str) -> None:
    """
    Worker for Lambda execution jobs

    Args:
        worker_id: The worker ID
    """
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

            msg = await ad.queue.recv_msg(analytiq_client, "lambda")
            if msg:
                logger.info(f"Worker {worker_id} processing Lambda msg: {msg}")
                try:
                    await ad.msg_handlers.process_lambda_msg(analytiq_client, msg)
                except Exception as e:
                    logger.error(f"Error processing Lambda message {msg.get('_id')}: {str(e)}")
                    # Mark message as failed
                    await ad.queue.delete_msg(analytiq_client, "lambda", str(msg["_id"]), status="failed")
            else:
                await asyncio.sleep(0.2)  # Avoid tight loop when no messages
                
        except Exception as e:
            logger.error(f"Worker {worker_id} encountered error: {str(e)}")
            await asyncio.sleep(1)  # Sleep longer on errors to prevent tight loop

async def main():
    # Create N_WORKERS workers of worker_ocr, worker_llm, and worker_lambda
    ocr_workers = [worker_ocr(f"ocr_{i}") for i in range(N_WORKERS)]
    llm_workers = [worker_llm(f"llm_{i}") for i in range(N_WORKERS)]
    lambda_workers = [worker_lambda(f"lambda_{i}") for i in range(N_WORKERS)]

    # Run all workers concurrently
    await asyncio.gather(*ocr_workers, *llm_workers, *lambda_workers)

if __name__ == "__main__":
    try:    
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, exiting")
