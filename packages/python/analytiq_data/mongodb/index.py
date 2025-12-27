"""
Database utility functions for index management
"""
import logging
from typing import List, Tuple
from motor.motor_asyncio import AsyncIOMotorCollection

logger = logging.getLogger(__name__)


async def ensure_index(
    collection: AsyncIOMotorCollection,
    index_spec: List[Tuple[str, int]],
    index_name: str,
    background: bool = True,
    drop_other_indexes: bool = True
) -> bool:
    """
    Ensure an index exists on a collection, creating it idempotently.
    
    This function:
    1. Lists all existing indexes
    2. Optionally drops all indexes except _id_ and the target index (if it exists)
    3. Creates the target index only if it doesn't exist
    
    Args:
        collection: The MongoDB collection to create the index on
        index_spec: List of tuples specifying the index fields and direction,
                   e.g., [("organization_id", 1), ("timestamp", -1)]
        index_name: Name for the index
        background: Whether to create the index in the background (non-blocking)
        drop_other_indexes: If True, drop all other indexes except _id_ and target index
        
    Returns:
        True if the index was created, False if it already existed
        
    Raises:
        Exception: If index creation fails
    """
    try:
        # List existing indexes
        existing_indexes = await collection.list_indexes().to_list(length=None)
        index_names = [idx["name"] for idx in existing_indexes]
        
        index_exists = index_name in index_names
        
        # Drop other indexes if requested
        if drop_other_indexes:
            for existing_index_name in index_names:
                if existing_index_name != "_id_" and existing_index_name != index_name:
                    try:
                        await collection.drop_index(existing_index_name)
                        logger.info(f"Dropped existing index {existing_index_name} from {collection.name}")
                    except Exception as e:
                        logger.warning(f"Failed to drop index {existing_index_name} from {collection.name}: {e}")
        
        # Create the index only if it doesn't exist
        if not index_exists:
            await collection.create_index(
                index_spec,
                name=index_name,
                background=background
            )
            logger.info(f"Created index {index_name} on {collection.name} with spec {index_spec}")
            return True
        else:
            logger.info(f"Index {index_name} already exists on {collection.name}")
            return False
            
    except Exception as e:
        logger.error(f"Error managing index {index_name} on {collection.name}: {e}")
        raise

