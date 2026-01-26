# DocRouter Python SDK Installation and Usage Guide

## Overview

The DocRouter Python SDK provides a Python client library for interacting with the DocRouter API. It enables developers to integrate document processing, OCR, LLM operations, schema management, prompt management, and tag management into their Python applications.

## Installation

### Prerequisites

- **Python 3.8+**
- **pip** package manager
- **DocRouter API access** with organization credentials

### Install from PyPI

```bash
pip install docrouter-sdk
```

### From TestPyPI (pre-release validation)

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ docrouter-sdk
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

## API Modules

The client library provides the following API modules:

- `client.documents` - Document management
- `client.ocr` - OCR operations
- `client.llm` - LLM analysis operations
- `client.schemas` - Schema management
- `client.prompts` - Prompt management
- `client.tags` - Tag management

## Documents API

### Upload Documents

```python
import base64
from docrouter_sdk import DocRouterClient

client = DocRouterClient(
    base_url="https://app.docrouter.ai/fastapi",
    api_token="your_organization_api_token"
)

organization_id = "your_organization_id"

# Upload a document
with open("invoice.pdf", "rb") as f:
    content = base64.b64encode(f.read()).decode("utf-8")

result = client.documents.upload(organization_id, [{
    "name": "invoice.pdf",
    "content": content,  # Base64 encoded content (can be data URL or plain base64)
    "tag_ids": ["tag_id_1", "tag_id_2"],  # Optional list of tag IDs
    "metadata": {"key": "value"}  # Optional metadata key-value pairs
}])

print(f"Uploaded document ID: {result['documents'][0]['document_id']}")
```

### List Documents

```python
# List documents with pagination and filters
documents = client.documents.list(
    organization_id,
    skip=0,                    # Number of documents to skip
    limit=10,                  # Maximum number of documents to return
    tag_ids=["tag_id_1"],      # Optional: filter by tag IDs
    name_search="invoice",     # Optional: search term for document names
    metadata_search={"key": "value"}  # Optional: filter by metadata key-value pairs
)

print(f"Found {documents.total_count} documents")
for doc in documents.documents:
    print(f"  - {doc.document_name} (ID: {doc.id})")
```

### Get Document

```python
document = client.documents.get(organization_id, document_id)
print(f"Document: {document.document_name}")
print(f"State: {document.state}")
print(f"Tags: {document.tag_ids}")
print(f"Metadata: {document.metadata}")
```

### Update Document

```python
result = client.documents.update(
    organization_id,
    document_id,
    document_name="New Name",           # Optional: new name for the document
    tag_ids=["tag_id_1", "tag_id_2"],  # Optional: list of tag IDs
    metadata={"key": "updated_value"}   # Optional: metadata key-value pairs
)
```

### Delete Document

```python
result = client.documents.delete(organization_id, document_id)
print(result)  # Status message
```

## OCR API

### Get OCR Blocks

```python
blocks = client.ocr.get_blocks(organization_id, document_id)
# Returns dict containing OCR block data with position and text information
```

### Get OCR Text

```python
# Get text for all pages
text = client.ocr.get_text(organization_id, document_id)
print(f"OCR Text: {text[:100]}...")

# Get text for a specific page (1-based)
page_text = client.ocr.get_text(organization_id, document_id, page_num=1)
```

### Get OCR Metadata

```python
metadata = client.ocr.get_metadata(organization_id, document_id)
print(f"Number of pages: {metadata['n_pages']}")
print(f"OCR date: {metadata['ocr_date']}")
```

## LLM API

### List LLM Models

```python
models = client.llm.list_models()
print(f"Chat models: {len(models.chat_models)}")
print(f"Embedding models: {len(models.embedding_models)}")
```

### Run LLM Analysis

```python
result = client.llm.run(
    organization_id,
    document_id,
    prompt_revid="default",  # The prompt revision ID to use
    force=False              # Whether to force a new run even if results exist
)
print(f"LLM Analysis status: {result.status}")
```

### Get LLM Result

```python
llm_result = client.llm.get_result(
    organization_id,
    document_id,
    prompt_revid="default",  # The prompt revision ID to retrieve
    fallback=False           # Whether to fallback to previous version if current not found
)
print(f"LLM Result: {llm_result.llm_result}")
print(f"Is verified: {llm_result.is_verified}")
```

### Update LLM Result

```python
updated_result = client.llm.update_result(
    organization_id,
    document_id,
    updated_llm_result={"key": "updated_value"},  # The updated LLM result
    prompt_revid="default",                        # The prompt revision ID to update
    is_verified=True                               # Whether the result is verified
)
```

### Delete LLM Result

```python
result = client.llm.delete_result(
    organization_id,
    document_id,
    prompt_revid="default"  # The prompt revision ID to delete
)
```

## Schemas API

### Create Schema

```python
schema_config = {
    "name": "Invoice Schema",
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "invoice_extraction",
            "schema": {
                "type": "object",
                "properties": {
                    "invoice_date": {
                        "type": "string",
                        "description": "invoice date"
                    }
                },
                "required": ["invoice_date"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
}
new_schema = client.schemas.create(organization_id, schema_config)
print(f"Created schema: {new_schema.schema_revid}")
```

### List Schemas

```python
schemas = client.schemas.list(
    organization_id,
    skip=0,    # Number of schemas to skip
    limit=10   # Maximum number of schemas to return
)
print(f"Found {schemas.total_count} schemas")
```

### Get Schema

```python
schema = client.schemas.get(organization_id, schema_revid)
print(f"Schema: {schema.name}")
print(f"Version: {schema.schema_version}")
```

### Update Schema

```python
updated_schema = client.schemas.update(
    organization_id,
    schema_id,      # The schema ID (not revision ID)
    schema_config   # The updated schema configuration
)
```

### Delete Schema

```python
result = client.schemas.delete(organization_id, schema_id)
```

### Validate Data Against Schema

```python
validation_result = client.schemas.validate(
    organization_id,
    schema_id,
    {"invoice_date": "2023-01-01"}  # Data to validate
)
```

## Prompts API

### Create Prompt

```python
prompt_config = {
    "name": "Invoice Extractor",
    "content": "Extract the following fields from the invoice...",
    "schema_id": "schema_id_here",      # Optional: associated schema ID
    "schema_version": 1,                 # Optional: schema version
    "tag_ids": ["tag_id_1", "tag_id_2"], # Optional: list of tag IDs
    "model": "gpt-4o-mini",              # LLM model to use
    "kb_id": "kb_id_here"                # Optional: knowledge base ID for RAG
}
new_prompt = client.prompts.create(organization_id, prompt_config)
print(f"Created prompt: {new_prompt.prompt_revid}")
```

### List Prompts

```python
prompts = client.prompts.list(
    organization_id,
    skip=0,                          # Number of prompts to skip
    limit=10,                        # Maximum number of prompts to return
    document_id="doc_id",            # Optional: filter by document ID
    tag_ids=["tag_id_1", "tag_id_2"] # Optional: filter by tag IDs
)
print(f"Found {prompts.total_count} prompts")
```

### Get Prompt

```python
prompt = client.prompts.get(organization_id, prompt_revid)
print(f"Prompt: {prompt.name}")
print(f"Version: {prompt.prompt_version}")
```

### Update Prompt

```python
updated_prompt = client.prompts.update(
    organization_id,
    prompt_id,      # The prompt ID (not revision ID)
    prompt_config   # The updated prompt configuration
)
```

### Delete Prompt

```python
result = client.prompts.delete(organization_id, prompt_id)
```

## Tags API

### Create Tag

```python
tag_config = {
    "name": "Invoices",
    "color": "#FF5733",              # Optional: hex color code
    "description": "All invoice documents"  # Optional: description
}
new_tag = client.tags.create(organization_id, tag_config)
print(f"Created tag: {new_tag.id}")
```

### List Tags

```python
tags = client.tags.list(
    organization_id,
    skip=0,   # Number of tags to skip
    limit=10  # Maximum number of tags to return
)
print(f"Found {tags.total_count} tags")
for tag in tags.tags:
    print(f"  - {tag.name} (ID: {tag.id})")
```

### Update Tag

```python
updated_tag = client.tags.update(
    organization_id,
    tag_id,
    tag_config  # Updated tag configuration
)
```

### Delete Tag

```python
result = client.tags.delete(organization_id, tag_id)
```

## Example: Complete Workflow

```python
import base64
from docrouter_sdk import DocRouterClient

# Initialize the client
client = DocRouterClient(
    base_url="https://app.docrouter.ai/fastapi",
    api_token="your_organization_api_token"
)

organization_id = "your_organization_id"

# 1. Create a tag
tag_config = {
    "name": "Invoices",
    "color": "#FF5733",
    "description": "All invoice documents"
}
tag = client.tags.create(organization_id, tag_config)
print(f"Created tag: {tag.id}")

# 2. Upload a document with the tag
with open("invoice.pdf", "rb") as f:
    content = base64.b64encode(f.read()).decode("utf-8")

result = client.documents.upload(organization_id, [{
    "name": "invoice.pdf",
    "content": content,
    "tag_ids": [tag.id],
    "metadata": {"category": "invoice"}
}])

document_id = result['documents'][0]['document_id']
print(f"Uploaded document ID: {document_id}")

# 3. Get OCR text
ocr_text = client.ocr.get_text(organization_id, document_id)
print(f"OCR Text: {ocr_text[:100]}...")

# 4. Run LLM analysis
llm_result = client.llm.run(organization_id, document_id, prompt_revid="default")
print(f"LLM Analysis status: {llm_result.status}")

# 5. Get LLM result
result = client.llm.get_result(organization_id, document_id, prompt_revid="default")
print(f"LLM Result: {result.llm_result}")
```

## Error Handling

The client handles API errors by raising exceptions with detailed error messages:

```python
try:
    result = client.documents.get(organization_id, "invalid_id")
except Exception as e:
    print(f"API Error: {str(e)}")
```

## Package Information

- **Package Name**: `docrouter-sdk`
- **Current Version**: 0.1.5
- **Python Requirement**: >=3.8
- **License**: Apache-2.0
- **Dependencies**: requests>=2.31.0, pydantic>=2.0.0
- **Repository**: https://github.com/analytiq/doc-router

## Additional Resources

For more comprehensive examples and usage patterns, see:

- **GitHub Repository**: [https://github.com/analytiq/doc-router](https://github.com/analytiq/doc-router)
- **Unit Tests**: `packages/python/sdk/tests/`
- **Examples**: `packages/python/sdk/examples/`
- **SDK README**: `packages/python/sdk/README.md`
