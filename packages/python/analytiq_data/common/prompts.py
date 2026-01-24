from datetime import datetime, UTC
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional

import analytiq_data as ad

async def get_prompt_id(analytiq_client, prompt_name: str, organization_id: str) -> str:
    """
    Get a prompt ID by its name

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        prompt_name: str
            Prompt name
        organization_id: str
            Organization ID
    Returns:
        str
            Prompt ID
        int
            Prompt version
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]

    collection = db["prompts"]
    elem = await collection.find_one({"name": prompt_name, "organization_id": organization_id})
    if elem is None:
        raise ValueError(f"Prompt {prompt_name} not found in organization {organization_id}")
    return str(elem["_id"]), elem["prompt_version"]

async def get_prompt_revid(analytiq_client,
                           prompt_id: str,
                           prompt_version: int) -> str:
    """
    Get a prompt revision ID by its ID and version
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["prompt_revisions"]
    elem = await collection.find_one({"prompt_id": prompt_id, "prompt_version": prompt_version})
    if elem is None:
        raise ValueError(f"Prompt {prompt_id} version {prompt_version} not found")
    return str(elem["_id"])

async def get_prompt_name(analytiq_client, prompt_id: str) -> str:
    """
    Get a prompt name by its ID
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["prompt_revisions"]
    elem = await collection.find_one({"_id": ObjectId(prompt_id)})
    if elem is None:
        raise ValueError(f"Prompt {prompt_id} not found")
    return elem["name"]

async def get_default_prompt_content(analytiq_client) -> str:
    """
    Get the default prompt content

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client

    Returns:
        str
            Prompt content
    """
    prompt = f"""Extract the document type, company name and address from the following text. 
    Return the result in JSON format with the following fields:
    - document_type: The type of document (e.g. "invoice", "purchase_order", "statement", "resume")
    - document_date: The date of the document, if not present, return ""
    - summary: A one line summary or description of the document.
    
    Examples:
    Input: "INVOICE ABC Corp. 123 Business St, New York, NY 10001 Invoice #12345"
    Output: {{
        "document_type": "invoice",
        "document_date": "",
        "summary": "Invoice for ABC Corp."
    }}
    
    Input: "Purchase Order XYZ Industries 456 Industrial Ave, Chicago, IL 60601, dated 2021-01-01"
    Output: {{
        "document_type": "purchase_order",
        "document_date": "2021-01-01",
        "summary": "Purchase Order for XYZ Industries"
    }}
    
    Input: "Statement of Account Global Trading Co. 789 Commerce Rd, Los Angeles, CA 90001"
    Output: {{
        "document_type": "statement",
        "document_date": "",
        "summary": "Statement of Account for Global Trading Co."
    }}

    Input: "Resume of John Doe, 123 Main St, Anytown, USA, 12345"
    Output: {{
        "document_type": "resume",
        "document_date": "",
        "summary": "Resume of John Doe"
    }}
    """
    return prompt

async def get_prompt_content(analytiq_client, prompt_id: str) -> str:
    """
    Get a prompt content by its ID
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        prompt_id: str
            Prompt ID

    Returns:
        str
            Prompt content
    """
    # Special case for the default prompt
    if prompt_id == "default":
        return await get_default_prompt_content(analytiq_client)

    # Get the prompt content
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["prompt_revisions"]
    
    elem = await collection.find_one({"_id": ObjectId(prompt_id)})
    if elem is None:
        raise ValueError(f"Prompt {prompt_id} not found")
    return elem["content"]

async def get_prompt_response_format(analytiq_client, prompt_id: str) -> dict:
    """
    Get a prompt response format by its ID
    
    Returns:
        dict: The schema in JSON Schema format
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["prompt_revisions"]
    elem = await collection.find_one({"_id": ObjectId(prompt_id)})
    if elem is None:
        raise ValueError(f"Prompt {prompt_id} not found")
    schema_id = elem.get("schema_id", None)
    schema_version = elem.get("schema_version", None)
    if schema_id is None or schema_version is None:
        return None

    # Get the schema from the name and version
    collection = db["schema_revisions"]
    elem = await collection.find_one({"schema_id": schema_id, "schema_version": schema_version})
    if elem is None:
        raise ValueError(f"Prompt {prompt_id}: Schema {schema_id} version {schema_version} not found")
    return elem["response_format"]

async def get_prompt_tag_ids(analytiq_client, prompt_id: str) -> list[str]:
    """
    Get a prompt tag IDs by its ID

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        prompt_id: str
            Prompt ID

    Returns:
        list[str]
            Prompt tag IDs
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["prompt_revisions"]
    elem = await collection.find_one({"_id": ObjectId(prompt_id)})
    return elem["tag_ids"]

async def get_prompt_kb_id(analytiq_client, prompt_id: str) -> Optional[str]:
    """
    Get the knowledge base ID associated with a prompt.
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        prompt_id: str
            Prompt revision ID
            
    Returns:
        Optional[str]: KB ID if prompt has one, None otherwise
    """
    # Special case for default prompt
    if prompt_id == "default":
        return None
    
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["prompt_revisions"]
    elem = await collection.find_one({"_id": ObjectId(prompt_id)})
    if elem is None:
        raise ValueError(f"Prompt {prompt_id} not found")
    return elem.get("kb_id")


async def get_prompt_revision_ids_by_tag_ids(analytiq_client, tag_ids: list[str], latest_version: bool = True) -> list[str]:
    """
    Get prompt revision IDs by tag IDs

    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        tag_ids: list[str]
            Tag IDs

    Returns:
        list[str]
            Prompt IDs
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["prompt_revisions"]
    elems = await collection.find({"tag_ids": {"$in": tag_ids}}).to_list(length=None)

    if not latest_version:
        # Return all prompt revision IDs
        prompt_revision_ids = [str(elem["_id"]) for elem in elems]
    else:
        # Eliminate elements that don't have the latest version
        elems2 = []
        for elem in elems:
            # Is there another element with the same prompt_id and a higher prompt_version?
            if not any(elem2["prompt_id"] == elem["prompt_id"] and elem2["prompt_version"] > elem["prompt_version"] for elem2 in elems):
                elems2.append(elem)

        prompt_revision_ids = [str(elem["_id"]) for elem in elems2]
    
    return prompt_revision_ids