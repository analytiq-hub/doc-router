# DocRouter Client Examples

This directory contains examples demonstrating how to use the DocRouter Client API.

## Basic Usage Example

The `basic_usage.py` example shows how to:
- Initialize the DocRouter client
- List documents, tags, and LLM models
- Handle errors gracefully

### Running the Example

```bash
# Set your API credentials as environment variables
export DOCROUTER_URL="https://app.docrouter.ai/fastapi"
# export DOCROUTER_URL="http://localhost:8000" # for local development
export DOCROUTER_API_TOKEN="your_actual_token_here"
export DOCROUTER_ORGANIZATION_ID="your_actual_org_id_here"

# Then run the example
./basic_docrouter_client.py
```