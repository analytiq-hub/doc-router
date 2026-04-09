import gridfs
from datetime import datetime, UTC
import os
import time
import asyncio
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
import logging

import analytiq_data as ad

logger = logging.getLogger(__name__)

async def get_blob_async(analytiq_client, bucket: str, key: str) -> dict:
    """
    Get the file asynchronously
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        bucket : str
            bucket name
        key : str
            blob key

    Returns:
        dict
            {"blob": bytes, "metadata": dict, "upload_date": datetime}
    """
    # Get the provider db
    mongo = analytiq_client.mongodb_async
    db_name = analytiq_client.env
    db = mongo[db_name]
    collection = db[f"{bucket}.files"]

    # Get the doc metadata
    file_doc = await collection.find_one({"filename": key})
    if file_doc is None:
        return None
    metadata = file_doc.get("metadata", None)
    upload_date = file_doc.get("uploadDate", None)

    # Download by file _id to avoid a second GridFS lookup by filename (extra round trip).
    fs_bucket = AsyncIOMotorGridFSBucket(db, bucket_name=bucket)
    stream = await fs_bucket.open_download_stream(file_doc["_id"])
    blob = await stream.read()

    blob_dict = {
        "blob": blob,
        "metadata": metadata,
        "upload_date": upload_date
    }
    return blob_dict

async def save_blob_async(analytiq_client, bucket: str, key: str, blob: bytes, metadata: dict, chunk_size_bytes: int = 8*1024*1024):
    """
    Save the file asynchronously
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        bucket : str
            bucket name
        key : str
            blob key
        blob : bytes
            blob blob
        metadata : dict
            blob metadata
        chunk_size_bytes : int
            chunk size in bytes (default: 1MB)
    """
    # Get the db
    mongo = analytiq_client.mongodb_async
    db_name = analytiq_client.env
    db = mongo[db_name]
    
    # Delete the old blob
    await delete_blob_async(analytiq_client, bucket, key)

    # Create a new GridFS bucket with smaller chunk size
    fs_bucket = AsyncIOMotorGridFSBucket(
        db, 
        bucket_name=bucket,
        chunk_size_bytes=chunk_size_bytes  # Use smaller chunks
    )
    
    logger.debug(f"Uploading blob {bucket}/{key} to mongodb with chunk size {chunk_size_bytes/1024/1024:.2f}MB")
    await fs_bucket.upload_from_stream(filename=key, source=blob, metadata=metadata)

async def delete_blob_async(analytiq_client, bucket:str, key:str):
    """
    Delete the blob asynchronously

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        bucket : str
            bucket name
        key : str
            blob key
    """
    # Get the db
    mongo = analytiq_client.mongodb_async
    db_name = analytiq_client.env
    db = mongo[db_name]
    fs_bucket = AsyncIOMotorGridFSBucket(db, bucket_name=bucket)

    # Remove the old blob with retry logic
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            # First, find the file document to get the _id
            files_collection = db[f"{bucket}.files"]
            file_docs = await files_collection.find({"filename": key}).to_list(length=None)
            
            if file_docs:
                for file_doc in file_docs:
                    # Delete using the _id from the file document
                    logger.debug(f"Deleting blob {bucket}/{key} with _id {file_doc['_id']}")
                    await fs_bucket.delete(file_doc["_id"])
                
                logger.debug(f"Blob {bucket}/{key} has been deleted.")
                
                # Verify deletion is complete
                verification_attempts = 3
                for _ in range(verification_attempts):
                    check_docs = await files_collection.find({"filename": key}).to_list(length=None)
                    if not check_docs:
                        break
                    await asyncio.sleep(retry_delay)
                else:
                    raise Exception(f"Failed to verify blob deletion for {bucket}/{key}")
                
            break  # Exit retry loop if successful
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to delete blob {bucket}/{key} after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Retry {attempt + 1}/{max_retries} for deleting {bucket}/{key}: {e}")
            await asyncio.sleep(retry_delay)