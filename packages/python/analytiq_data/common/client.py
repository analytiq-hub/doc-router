import os
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

import analytiq_data as ad

class AnalytiqClient:
    def __init__(self, env: str = "dev", name: str = None):
        self.env = env
        self.name = name
        self._mongodb_async_override: Any = None

    @property
    def mongodb_async(self) -> AsyncIOMotorClient:
        """Motor client for the current event loop (shared pool per loop)."""
        if self._mongodb_async_override is not None:
            return self._mongodb_async_override
        return ad.mongodb.get_mongodb_client_async()

    @mongodb_async.setter
    def mongodb_async(self, value: Any) -> None:
        self._mongodb_async_override = value

def get_analytiq_client(env: str = None, name: str = None) -> AnalytiqClient:
    """
    Get the AnalytiqClient.

    Args:
        env: The environment to connect to. Defaults to the environment variable "ENV".

    Returns:
        The AnalytiqClient.
    """
    if not env:
        env = os.getenv("ENV", "dev")
    return AnalytiqClient(env, name)

def get_async_db(analytiq_client: AnalytiqClient = None) -> AsyncIOMotorDatabase:
    """
    Get the async MongoDB database handle for the current environment.

    Args:
        analytiq_client: The AnalytiqClient. Defaults to the current environment client.

    Returns:
        The async database (``AsyncIOMotorDatabase``).
    """
    if not analytiq_client:
        analytiq_client = get_analytiq_client()
    return analytiq_client.mongodb_async[analytiq_client.env]
