import boto3, botocore
import aioboto3
from collections import defaultdict
import json
import re
import time
import asyncio
from datetime import datetime
import uuid
import logging
import os
import analytiq_data as ad
from typing import List, Optional, Union

logger = logging.getLogger(__name__)


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


OCR_TIMEOUT_SECS = _get_int_env("OCR_TIMEOUT_SECS", 600)  # 10 min


def ocr_result_blocks(ocr_json: Union[list, dict]) -> List[dict]:
    """
    Normalize OCR payload from :func:`run_textract` or persisted :func:`analytiq_data.common.ocr.get_ocr_json`:
    either a legacy flat list of blocks or a dict shaped like ``GetDocumentAnalysis`` / ``GetDocumentTextDetection``.
    """
    if isinstance(ocr_json, dict) and "Blocks" in ocr_json:
        return ocr_json["Blocks"]
    return ocr_json


def configure_textractor_logging(level: int = logging.WARNING) -> None:
    """
    Set the log level for ``textractor.parsers.response_parser``.

    Textract often returns ``KEY_VALUE_SET`` blocks whose relationships omit CHILD; textractor
    then emits one INFO line per block. That is normal and does not mean parsing failed.
    Call this before ``textractor`` parsing (e.g. ``parse_document_api_response``) when
    ``logging`` is configured at INFO and those lines are unwanted noise.
    """
    logging.getLogger("textractor.parsers.response_parser").setLevel(level)


async def run_textract(analytiq_client,
                       blob: bytes,
                       feature_types: list = [],
                       query_list: Optional[list] = None,
                       document_id: Optional[str] = None,
                       org_id: Optional[str] = None) -> dict:
    """
    Run textract on a blob and return merged API-shaped results.

    Args:
        analytiq_client: Analytiq client
        doc_blob: Bytes to be textracted
        feature_types: List of feature types, e.g. ["LAYOUT", "TABLES", "FORMS", "SIGNATURES"]
        query_list: List of queries

    Returns:
        Dict with ``Blocks`` (merged across pagination), ``DocumentMetadata``, and model version fields
        from Textract (``AnalyzeDocumentModelVersion`` for analysis jobs,
        ``DetectDocumentTextModelVersion`` for text-detection-only jobs). Use :func:`ocr_result_blocks`
        if you only need the block list (also accepts legacy stored lists).
    """
    # Get the async AWS client
    aws_client = await ad.aws.get_aws_client_async(analytiq_client)
    s3_bucket_name = aws_client.s3_bucket_name

    # Create a random s3 key
    s3_key = f"textract/tmp/{datetime.now().strftime('%Y-%m-%d')}/{uuid.uuid4()}"

    try:
        # Upload to S3 using async client
        async with aws_client.client('s3') as s3_client:
            await s3_client.put_object(Bucket=s3_bucket_name, Key=s3_key, Body=blob)

        # Start Textract job using async client
        async with aws_client.client('textract') as textract_client:
            if query_list is not None and len(query_list) > 0:
                query_list = [{'Text': '{}'.format(q)} for q in query_list]
                response = await textract_client.start_document_analysis(
                    DocumentLocation={
                        'S3Object': {
                            'Bucket': s3_bucket_name,
                            'Name': s3_key
                        }
                    },
                    FeatureTypes=feature_types + ["QUERIES"],
                    QueriesConfig = {'Queries': query_list}
                )
                get_completion_func = textract_client.get_document_analysis
            elif len(feature_types) > 0:
                response = await textract_client.start_document_analysis(
                    DocumentLocation={
                        'S3Object': {
                            'Bucket': s3_bucket_name,
                            'Name': s3_key
                        }
                    },
                    FeatureTypes=feature_types,
                )
                get_completion_func = textract_client.get_document_analysis
            else:
                response = await textract_client.start_document_text_detection(
                    DocumentLocation={
                        'S3Object': {
                            'Bucket': s3_bucket_name,
                            'Name': s3_key
                        }
                    }
                )
                get_completion_func = textract_client.get_document_text_detection

            job_id = response['JobId']

            # Log prefix: org_id/document_id when both present, else document_id, else empty
            if org_id and document_id:
                log_prefix = f"{org_id}/{document_id}"
            elif document_id:
                log_prefix = document_id
            else:
                log_prefix = ""

            # Check completion status with async polling and exponential backoff
            idx = 0
            # Use event loop time for robust elapsed timing even if system clock changes
            loop = asyncio.get_event_loop()
            start_time = loop.time()
            while True:
                elapsed = loop.time() - start_time
                if elapsed > OCR_TIMEOUT_SECS:
                    raise asyncio.TimeoutError(
                        f"Textract job {job_id} timed out after {OCR_TIMEOUT_SECS}s"
                    )

                status_response = await get_completion_func(JobId=job_id)
                status = status_response['JobStatus']
                prefix_part = f"{log_prefix}: " if log_prefix else ""
                logger.info(f"{analytiq_client.name}: {prefix_part}step {idx}: {status}")
                idx += 1

                if status in ["SUCCEEDED", "FAILED"]:
                    break

                # Use exponential backoff for polling - start with 1s, max 10s
                sleep_time = min(2 ** min(idx // 5, 3), 10)
                await asyncio.sleep(sleep_time)

            idx = 0
            if status == "SUCCEEDED":
                blocks = []
                document_metadata: Optional[dict] = None
                analyze_document_model_version: Optional[str] = None
                detect_document_text_model_version: Optional[str] = None
                first_result_page = True

                next_token = None
                while True:
                    # Get results with pagination
                    if next_token:
                        response = await get_completion_func(JobId=job_id, NextToken=next_token)
                    else:
                        response = await get_completion_func(JobId=job_id)

                    if first_result_page:
                        document_metadata = response.get("DocumentMetadata")
                        analyze_document_model_version = response.get("AnalyzeDocumentModelVersion")
                        detect_document_text_model_version = response.get(
                            "DetectDocumentTextModelVersion"
                        )
                        first_result_page = False

                    blocks.extend(response['Blocks'])

                    # Check for more results
                    next_token = response.get('NextToken', None)
                    
                    prefix_part = f"{log_prefix}: " if log_prefix else ""
                    logger.info(f"{analytiq_client.name}: {prefix_part}step {idx}: blocks len: {len(blocks)} next_token: {next_token}")
                    idx += 1
                    if not next_token:
                        break

                if not document_metadata:
                    page_blocks = [b for b in blocks if b.get("BlockType") == "PAGE"]
                    document_metadata = {
                        "Pages": len(page_blocks) if page_blocks else 1,
                    }

                return {
                    "Blocks": blocks,
                    "DocumentMetadata": document_metadata,
                    "AnalyzeDocumentModelVersion": analyze_document_model_version,
                    "DetectDocumentTextModelVersion": detect_document_text_model_version,
                }
            else:
                raise Exception(f"Textract document analysis failed: {status} for s3://{s3_bucket_name}/{s3_key}")
                
    except Exception as e:
        logger.error(f"Error running textract: {e}")
        raise e
    finally:
        # Delete the s3 object using async client
        try:
            async with aws_client.client('s3') as s3_client:
                await s3_client.delete_object(Bucket=s3_bucket_name, Key=s3_key)
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup S3 object {s3_key}: {cleanup_error}")    

def get_block_map(blocks: list) -> dict:
    """
    Construct a map of blocks

    Args:
        blocks : dict
            Textract blocks

    Returns:
        dict
            Block map
    """
    block_map = {}
    for block in blocks:
        block_id = block['Id']
        block_map[block_id] = block
    return block_map
    

def get_kv_map(blocks: list) -> dict:
    """
    Construct a map of keys and values parsed by textract

    Args:
        blocks: Textract blocks

    Returns:
        Key and value map
    """
    key_map = {}
    value_map = {}
    for block in blocks:
        block_id = block['Id']
        if block['BlockType'] == "KEY_VALUE_SET":
            if 'KEY' in block['EntityTypes']:
                key_map[block_id] = block
            else:
                value_map[block_id] = block

    return key_map, value_map


def get_kv_relationship(key_map: dict, value_map: dict, block_map: dict) -> dict:
    """
    Get the key and value relationships

    Args:
        key_map: Key map
        value_map: Value map
        block_map: Block map

    Returns:
        Key and value relationships
    """
    kvs = defaultdict(list)
    for _, key_block in key_map.items():
        value_block = find_value_block(key_block, value_map)
        key = get_text(key_block, block_map)
        val = get_text(value_block, block_map)
        kvs[key].append(val)
    return kvs

def find_value_block(key_block: dict, value_map: dict) -> dict:
    for relationship in key_block['Relationships']:
        if relationship['Type'] == 'VALUE':
            for value_id in relationship['Ids']:
                value_block = value_map[value_id]
    return value_block


def get_text(block: dict, blocks_map: dict) -> str:
    text = ''
    if 'Relationships' in block:
        for relationship in block['Relationships']:
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    word = blocks_map[child_id]
                    if word['BlockType'] == 'WORD':
                        text += word['Text'] + ' '
                    if word['BlockType'] == 'SELECTION_ELEMENT':
                        if word['SelectionStatus'] == 'SELECTED':
                            text += 'X '

    return text

def get_query_map(block_map: dict) -> dict:
    """
    Get the query map

    Args:
        block_map: Block map

    Returns:
        Query map
    """
    query_map = {}

    for _, block in block_map.items():
        if block["BlockType"] == "QUERY":
            query_text = block["Query"]["Text"]
            query_map[query_text] = None
            for relationship in block.get("Relationships", []):
                if relationship["Type"] == "ANSWER":
                    for value_id in relationship["Ids"]:
                        value_block = block_map[value_id]
                        answer_text = value_block["Text"]
                        query_map[query_text] = answer_text
    return query_map

def search_value(kvs: dict, search_key: str) -> list:
    """
    Search for a key in the key and value map

    Args:
        kvs: Key and value map
        search_key: Search key

    Returns:
        List of values
    """
    for key, value in kvs.items():
        if re.search(search_key, key, re.IGNORECASE):
            return value
        

def get_tables(block_map: dict) -> list:
    """
    Get the tables

    Args:
        block_map: Block map

    Returns:
        List of tables
    """
    tables = []
    for _, block in block_map.items():
        if block['BlockType'] == 'TABLE':
            table = {}
            for relationship in block.get('Relationships', []):
                if relationship['Type'] == 'CHILD':
                    for child_id in relationship['Ids']:
                        cell = next(b for _, b in block_map.items() if b['Id'] == child_id)
                        row_index = cell['RowIndex']
                        col_index = cell['ColumnIndex']
                        text = ''

                        for relationship2 in cell.get('Relationships', []):
                            if relationship2['Type'] == 'CHILD':
                                for child_id2 in relationship2['Ids']:
                                    child_block2 = block_map.get(child_id2, None)
                                    if child_block2 and 'Text' in child_block2:
                                        if text == "":
                                            text = child_block2['Text']
                                        else:
                                            text += " "
                                            text += child_block2['Text']

                        # print(json.dumps(cell))
                        # print(text)

                        # Save the cell text to the table
                        table.setdefault(row_index, {})[col_index] = text
            
            # Save the table to the list of tables
            tables += [table]

            #for row in sorted(table.keys()):
            #    print([table[row].get(col, '') for col in sorted(table[row].keys())])

    return tables

def get_page_text_map(block_map: dict) -> dict:
    """
    Get the page text map

    Args:
        block_map: Block map

    Returns:
        Page text map
    """
    page_text_map = {}
    for _, block in block_map.items():
        if block['BlockType'] == 'LINE':
            page = block['Page']
            if page not in page_text_map:
                page_text_map[page] = ""
            page_text_map[page] += block['Text'] + "\n"
    
    if len(page_text_map) == 0:
        return page_text_map

    max_page = max(page_text_map.keys())

    for page in range(1, max_page+1):
        if page not in page_text_map:
            page_text_map[page] = ""

    page_text_map = dict(sorted(page_text_map.items()))

    return page_text_map