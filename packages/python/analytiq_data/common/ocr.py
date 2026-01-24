from datetime import datetime, UTC
import os
import pickle
import analytiq_data as ad
import logging

logger = logging.getLogger(__name__)

OCR_BUCKET = "ocr"

async def get_ocr_json(analytiq_client, document_id: str) -> list:
    """Get OCR blocks supporting both old and new key formats"""
    # Try new format first
    key = f"{document_id}_json"
    ocr_blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)
    
    # Fall back to old format if not found
    if ocr_blob is None:
        key = f"{document_id}_list"
        ocr_blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)
        
    if ocr_blob is None:
        return None
        
    return pickle.loads(ocr_blob["blob"])
   

async def save_ocr_json(analytiq_client, document_id:str, ocr_json:list, metadata:dict=None):
    """Save OCR JSON using new format"""
    key = f"{document_id}_json"
    ocr_bytes = pickle.dumps(ocr_json)
    size_mb = len(ocr_bytes) / 1024 / 1024
    logger.info(f"Saving OCR json for {document_id} with metadata: {metadata} size: {size_mb:.2f}MB")
    await ad.mongodb.save_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key, blob=ocr_bytes, metadata=metadata)
    
    logger.info(f"OCR JSON for {document_id} has been saved.")

async def delete_ocr_json(analytiq_client, document_id:str):
    """
    Delete the OCR JSON

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id
    """
    key = f"{document_id}_json"
    await ad.mongodb.delete_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)

    logger.debug(f"OCR JSON for {document_id} has been deleted.")

async def get_ocr_text(analytiq_client, document_id:str, page_idx:int=None) -> str:
    """
    Get the OCR text
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id
        page_idx : int
            page index. If None, return the whole OCR text.

    Returns:
        str
            OCR text
    """
    key = f"{document_id}_text"
    if page_idx is not None:
        key += f"_page_{page_idx}"
    blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)
    if blob is None:
        return None
    return blob["blob"].decode("utf-8")
   

async def save_ocr_text(analytiq_client, document_id:str, ocr_text:str, page_idx:int=None, metadata:dict=None):
    """
    Save the OCR text
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id
        ocr_text : str
            OCR text
        page_idx : int
            page index
        metadata : dict
            OCR metadata
    """
    key = f"{document_id}_text"
    if page_idx is not None:
        key += f"_page_{page_idx}"
    
    # Convert the text to bytes 
    ocr_text_bytes = ocr_text.encode("utf-8")

    # Save the blob
    await ad.mongodb.save_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key, blob=ocr_text_bytes, metadata=metadata)
    
    logger.debug(f"OCR text for {document_id} page {page_idx} has been saved.")

async def delete_ocr_text(analytiq_client, document_id:str, page_idx:int=None):
    """
    Delete the OCR text

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id
        page_idx : int
            page index
    """
    key = f"{document_id}_text"
    if page_idx is not None:
        key += f"_page_{page_idx}"
    await ad.mongodb.delete_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)

    logger.debug(f"OCR text for {document_id} page {page_idx} has been deleted.")

async def delete_ocr_all(analytiq_client, document_id:str):
    """
    Delete the OCR

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id
    """
    n_pages = await get_ocr_n_pages(analytiq_client, document_id)
    for page_idx in range(n_pages):
        await delete_ocr_text(analytiq_client, document_id, page_idx)
    await delete_ocr_text(analytiq_client, document_id)
    await delete_ocr_json(analytiq_client, document_id)

async def save_ocr_text_from_list(analytiq_client, document_id:str, ocr_json:list, metadata:dict=None, force:bool=False):
    """
    Save the OCR text from the OCR list
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id
        ocr_json : list
            OCR list
        metadata : dict
            OCR metadata
        force : bool
            Whether to force the processing
    """
    block_map = ad.aws.textract.get_block_map(ocr_json)
    page_text_map = ad.aws.textract.get_page_text_map(block_map)

    if not force:
        ocr_text = await get_ocr_text(analytiq_client, document_id)
        if ocr_text is not None:
            logger.info(f"OCR text for {document_id} already exists. Returning.")
            return
    else:
        # Remove the old OCR text, if any
        await delete_ocr_text(analytiq_client, document_id)
        for page_idx in range(len(page_text_map)):
            await delete_ocr_text(analytiq_client, document_id, page_idx)
    
    # Record the number of pages in the metadata
    if metadata is None:
        metadata = {}
    metadata["n_pages"] = len(page_text_map)
    
    # Save the new OCR text
    for page_num, page_text in page_text_map.items():
        page_idx = int(page_num) - 1
        await save_ocr_text(analytiq_client, document_id, page_text, page_idx, metadata)
        logger.info(f"OCR text for {document_id} page {page_idx} has been saved.")

    text = "\n".join(page_text_map.values())
    logger.info(f"Saving OCR text for {document_id} with metadata: {metadata} length: {len(text)}")
    await save_ocr_text(analytiq_client, document_id, text, metadata=metadata)

    logger.info(f"OCR text for {document_id} has been saved.")

async def get_ocr_metadata(analytiq_client, document_id:str) -> dict:
    """
    Get the OCR metadata
    """
    blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=f"{document_id}_text")
    if blob is None:
        return None

    metadata = {
        "n_pages": blob["metadata"].get("n_pages", 0),
        "ocr_date": blob.get("upload_date", None)
    }
    return metadata

async def get_ocr_n_pages(analytiq_client, document_id:str) -> int:
    """
    Get the number of pages in the OCR text

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        document_id : str
            document id

    Returns:
        int
            Number of pages in the OCR text
    """
    key = f"{document_id}_text"
    blob = await ad.mongodb.get_blob_async(analytiq_client, bucket=OCR_BUCKET, key=key)
    if blob is None:
        return 0
    if blob.get("metadata") is None:
        return 0
    return blob["metadata"].get("n_pages", 0)
