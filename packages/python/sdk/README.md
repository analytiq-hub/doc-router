# DocRouter Python SDK

A Python client library for the Document Router API.

## Quick Start
* Install from PyPI (recommended):
  ```bash
  pip install docrouter-sdk
  ```
* Get your DocRouter organization ID from the URL, e.g. `https://app.docrouter.ai/orgs/<docrouter_org_id>`
* Create an organization token. 
* Run the `basic_docrouter_client.py` example:
  ```bash
  export DOCROUTER_URL="https://app.docrouter.ai/fastapi"
  # export DOCROUTER_URL="http://localhost:8000" # for local development
  export DOCROUTER_ORG_ID=<docrouter_org_id>
  export DOCROUTER_ORG_API_TOKEN=<docrouter_org_api_token> 
  python packages/python/sdk/examples/basic_docrouter_client.py
```

## Installation

### From PyPI (production)
```bash
pip install docrouter-sdk
```

### From TestPyPI (pre-release validation)
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ docrouter-sdk
```

### Local editable install (development)
```bash
cd packages/python/sdk
pip install -e .
```

## Usage

```python
from docrouter_sdk import DocRouterClient

# Initialize the client
client = DocRouterClient(
    base_url="https://api.analytiq.ai",  # Replace with your API URL
    api_token="your_api_token"           # Replace with your API token
)

# Working with documents
organization_id = "your_organization_id"

# List documents
documents = client.documents.list(organization_id)
print(f"Found {documents.total_count} documents")

# Upload a document
import base64
with open("sample.pdf", "rb") as f:
    content = base64.b64encode(f.read()).decode("utf-8")

result = client.documents.upload(organization_id, [{
    "name": "sample.pdf",
    "content": content,
    "tag_ids": []
}])
print(f"Uploaded document: {result['documents'][0]['document_id']}")

# Get OCR text from a document
document_id = "document_id_here"
ocr_text = client.ocr.get_text(organization_id, document_id)
print(f"OCR Text: {ocr_text[:100]}...")

# Run LLM analysis
prompt_id = "default"
result = client.llm.run(organization_id, document_id, prompt_id)
print(f"LLM Analysis status: {result.status}")

# Working with schemas
schemas = client.schemas.list(organization_id)
print(f"Found {schemas.total_count} schemas")

# Working with prompts
prompts = client.prompts.list(organization_id)
print(f"Found {prompts.total_count} prompts")

# Working with tags
tags = client.tags.list(organization_id)
print(f"Found {tags.total_count} tags")
```

## API Modules

The client library provides the following API modules:

### Documents API

```python
# List documents
response = client.documents.list(organization_id, skip=0, limit=10, tag_ids=["tag1", "tag2"])

# Get a document
document = client.documents.get(organization_id, document_id)

# Update a document
client.documents.update(organization_id, document_id, document_name="New Name", tag_ids=["tag1"])

# Delete a document
client.documents.delete(organization_id, document_id)
```

### OCR API

```python
# Get OCR blocks
blocks = client.ocr.get_blocks(organization_id, document_id)

# Get OCR text
text = client.ocr.get_text(organization_id, document_id, page_num=1)

# Get OCR metadata
metadata = client.ocr.get_metadata(organization_id, document_id)
print(f"Number of pages: {metadata.n_pages}")
```

### LLM API

```python
# List LLM models
models = client.llm.list_models()

# Run LLM analysis
result = client.llm.run(organization_id, document_id, prompt_id="default", force=False)

# Get LLM result
llm_result = client.llm.get_result(organization_id, document_id, prompt_id="default")

# Update LLM result
updated_result = client.llm.update_result(
    organization_id, 
    document_id,
    updated_llm_result={"key": "value"},
    prompt_id="default",
    is_verified=True
)

# Delete LLM result
client.llm.delete_result(organization_id, document_id, prompt_id="default")
```

### Schemas API

```python
# Create a schema
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

# List schemas
schemas = client.schemas.list(organization_id)

# Get a schema
schema = client.schemas.get(organization_id, schema_id)

# Update a schema
updated_schema = client.schemas.update(organization_id, schema_id, schema_config)

# Delete a schema
client.schemas.delete(organization_id, schema_id)

# Validate data against a schema
validation_result = client.schemas.validate(organization_id, schema_id, {"invoice_date": "2023-01-01"})
```

### Prompts API

```python
# Create a prompt
prompt_config = {
    "name": "Invoice Extractor",
    "content": "Extract the following fields from the invoice...",
    "schema_id": "schema_id_here",
    "schema_version": 1,
    "tag_ids": ["tag1", "tag2"],
    "model": "gpt-4o-mini"
}
new_prompt = client.prompts.create(organization_id, prompt_config)

# List prompts
prompts = client.prompts.list(organization_id, document_id="doc_id", tag_ids=["tag1"])

# Get a prompt
prompt = client.prompts.get(organization_id, prompt_id)

# Update a prompt
updated_prompt = client.prompts.update(organization_id, prompt_id, prompt_config)

# Delete a prompt
client.prompts.delete(organization_id, prompt_id)
```

### Tags API

```python
# Create a tag
tag_config = {
    "name": "Invoices",
    "color": "#FF5733",
    "description": "All invoice documents"
}
new_tag = client.tags.create(organization_id, tag_config)

# List tags
tags = client.tags.list(organization_id)

# Update a tag
updated_tag = client.tags.update(organization_id, tag_id, tag_config)

# Delete a tag
client.tags.delete(organization_id, tag_id)
```

## Error Handling

The client handles API errors by raising exceptions with detailed error messages:

```python
try:
    result = client.documents.get(organization_id, "invalid_id")
except Exception as e:
    print(f"API Error: {str(e)}")
```

## License

Apache Software 2.0
