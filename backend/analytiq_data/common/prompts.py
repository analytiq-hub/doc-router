from datetime import datetime, UTC
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

import analytiq_data as ad


async def get_prompt(analytiq_client, prompt_id: str) -> dict:
    """
    Get a prompt by its ID
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        prompt_id: str
            Prompt ID

    Returns:
        dict
            Prompt metadata    
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["prompts"]
    
    return await collection.find_one({"_id": ObjectId(prompt_id)})

async def get_prompt_ids_by_tag(analytiq_client, tag: str) -> list[dict]:
    """
    Get all prompt ids that have the given tag in their tags array
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["prompts"]
    
    return await collection.find({"tags": tag}).to_list(length=None)