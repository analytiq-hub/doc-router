#!/usr/bin/env python3
"""Standalone database migration runner.

Used by:
  - Helm pre-upgrade/pre-install Job hook (Kubernetes)
  - Docker Compose migrate service (runs before backend starts)
  - Manual: python3 packages/python/migrate.py
"""
import asyncio
import os
import sys

cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cwd)

import analytiq_data as ad


async def main():
    ad.common.setup()
    client = ad.common.get_analytiq_client()
    try:
        await ad.migrations.run_migrations(client)
        print("Migrations complete.")
    finally:
        await ad.mongodb.close_shared_async_client()


if __name__ == "__main__":
    asyncio.run(main())
