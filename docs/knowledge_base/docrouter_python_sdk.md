# DocRouter Python SDK Installation and Usage Guide

## Overview

The DocRouter Python SDK provides a Python client library for interacting with the DocRouter API. It enables developers to integrate document processing, OCR, LLM operations, and organization management into their Python applications.

## Installation

### Prerequisites

- **Python 3.8+**
- **pip** package manager
- **DocRouter API access** with organization credentials

### Install from PyPI

```bash
pip install docrouter-sdk
```

### Local Development Installation

```bash
cd packages/python/sdk
pip install -e .
```

## Basic Usage

### Initialize the Client

```python
from docrouter_sdk import DocRouterClient

# Initialize the client
client = DocRouterClient(
    base_url="https://app.docrouter.ai/fastapi",  # DocRouter API URL
    api_token="your_organization_api_token"       # Your organization API token
)

# Your organization ID (found in the URL: https://app.docrouter.ai/orgs/<org_id>)
organization_id = "your_organization_id"
```

### Environment Variables

```bash
export DOCROUTER_URL="https://app.docrouter.ai/fastapi"
export DOCROUTER_ORG_ID="your_organization_id"
export DOCROUTER_ORG_API_TOKEN="your_organization_api_token"
```

```python
import os
from docrouter_sdk import DocRouterClient

client = DocRouterClient(
    base_url=os.getenv("DOCROUTER_URL"),
    api_token=os.getenv("DOCROUTER_ORG_API_TOKEN")
)

organization_id = os.getenv("DOCROUTER_ORG_ID")
```

## Example: Upload Document with Tag

```python
import base64
from docrouter_sdk import DocRouterClient

# Initialize the client
client = DocRouterClient(
    base_url="https://app.docrouter.ai/fastapi",
    api_token="your_organization_api_token"
)

organization_id = "your_organization_id"

# First, create a tag
tag_config = {
    "name": "Invoices",
    "color": "#FF5733",
    "description": "All invoice documents"
}

tag = client.tags.create(organization_id, tag_config)
print(f"Created tag: {tag.tag_id}")

# Upload a document with the tag
with open("invoice.pdf", "rb") as f:
    content = base64.b64encode(f.read()).decode("utf-8")

result = client.documents.upload(organization_id, [{
    "name": "invoice.pdf",
    "content": content,
    "tag_ids": [tag.tag_id]
}])

print(f"Uploaded document ID: {result['documents'][0]['document_id']}")
```

## Additional Examples

For more comprehensive examples and usage patterns, see the unit tests and examples in the GitHub repository:

- **GitHub Repository**: [https://github.com/analytiq/doc-router](https://github.com/analytiq/doc-router)
- **Unit Tests**: `packages/python/sdk/tests/`
- **Examples**: `packages/python/sdk/examples/`

## Package Information

- **Package Name**: `docrouter-sdk`
- **Current Version**: 0.1.5
- **Python Requirement**: >=3.8
- **License**: Apache-2.0
- **Dependencies**: requests>=2.31.0, pydantic>=2.0.0
