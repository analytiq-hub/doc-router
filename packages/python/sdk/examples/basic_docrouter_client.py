#! /usr/bin/env python3

import os
from docrouter_sdk import DocRouterClient

DOCROUTER_ORG_ID = os.getenv("DOCROUTER_ORG_ID")
if not DOCROUTER_ORG_ID:
    raise ValueError("DOCROUTER_ORG_ID is not set")

DOCROUTER_URL = os.getenv("DOCROUTER_URL", "http://localhost:8000")
if not DOCROUTER_URL:
    raise ValueError("DOCROUTER_URL is not set")

DOCROUTER_ORG_API_TOKEN = os.getenv("DOCROUTER_ORG_API_TOKEN")
if not DOCROUTER_ORG_API_TOKEN:
    raise ValueError("DOCROUTER_ORG_API_TOKEN is not set")

# Initialize the client
client = DocRouterClient(
    base_url=DOCROUTER_URL,            # Replace with your DocRouter URL
    api_token=DOCROUTER_ORG_API_TOKEN  # Replace with your organization API token
)

# Example: List documents
organization_id = DOCROUTER_ORG_ID  # Replace with your organization ID
documents = client.documents.list(organization_id)
print(f"Found {documents.total_count} documents")

# Example: List tags
tags = client.tags.list(organization_id)
print(f"Found {tags.total_count} tags")
