from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import os

import analytiq_data as ad

# Module-level variables
ANALYTIQ_CLIENT: Optional[ad.common.AnalytiqClient] = None
DB: Optional[AsyncIOMotorDatabase] = None
ENV: Optional[str] = None

def init_globals(env: str):
    """Initialize global variables"""
    ad.log.debug(f"Initializing globals for env: {env}")  # This will only print once
    
    global ANALYTIQ_CLIENT, DB, ENV, FASTAPI_SECRET
    ENV = env
    
    # Get MongoDB client
    ANALYTIQ_CLIENT = ad.common.get_analytiq_client(env=env)
    DB = ANALYTIQ_CLIENT.mongodb_async[env]

def get_db() -> AsyncIOMotorDatabase:
    """Get database instance"""
    if DB is None:
        raise RuntimeError("Database not initialized. Call init_globals() first.")
    return DB

def get_analytiq_client():
    """Get analytiq client instance"""
    if ANALYTIQ_CLIENT is None:
        raise RuntimeError("Analytiq client not initialized. Call init_globals() first.")
    return ANALYTIQ_CLIENT

def get_env() -> str:
    """Get environment"""
    if ENV is None:
        raise RuntimeError("Environment not initialized. Call init_globals() first.")
    return ENV 
    