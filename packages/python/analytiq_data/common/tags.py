from datetime import datetime, UTC
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import logging

import analytiq_data as ad

logger = logging.getLogger(__name__)

# Shared UI/defaults constant.
# Keep this in one place so both API routes and agent tools remain consistent.
DEFAULT_TAG_COLOR = "#3B82F6"

async def get_tag_id(analytiq_client, tag_name: str) -> str:
    """
    Get a tag by its ID
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        tag_name: str
            Tag name

    Returns:
        str
            Tag ID
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["tags"]

    # Print all collection elements
    elements = await collection.find().to_list(length=None)
    logger.info(elements)

    logger.info(f"db_name: {db_name}")
    # List all collections
    collections = await db.list_collection_names()
    logger.info(f"collections: {collections}")
    
    element = await collection.find_one({"name": tag_name})
    if element is None:
        raise ValueError(f"Tag {tag_name} not found")
    return str(element["_id"])

async def get_tag_name(analytiq_client, tag_id: str) -> str:
    """
    Get a tag by its ID
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        tag_id: str
            Tag ID

    Returns:
        str
            Tag name
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["tags"]

    element = await collection.find_one({"_id": ObjectId(tag_id)})
    if element is None:
        raise ValueError(f"Tag {tag_id} not found")
    return element["name"]

async def get_tag_ids(analytiq_client, tag_names: list[str]) -> list[str]:
    """
    Get all tag IDs
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        tag_names: list[str]
            Tag names

    Returns:
        list[str]
            Tag IDs
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["tags"]
    return [str(tag["_id"]) for tag in await collection.find().to_list(length=None)]

async def get_tag_names(analytiq_client, tag_ids: list[str]) -> list[str]:
    """
    Get all tag names
    
    Args:
        analytiq_client: AnalytiqClient
            The analytiq client
        tag_ids: list[str]
            Tag IDs

    Returns:
        list[str]
            Tag names
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    collection = db["tags"]
    return [tag["name"] for tag in await collection.find({"_id": {"$in": [ObjectId(tag_id) for tag_id in tag_ids]}}).to_list(length=None)]
