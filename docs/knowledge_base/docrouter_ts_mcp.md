# DocRouter MCP Server Installation and Setup Guide

## Overview

The DocRouter MCP (Model Context Protocol) Server provides AI applications with seamless access to DocRouter's document processing capabilities. This guide covers everything you need to know to install, configure, and use the DocRouter MCP server.

## What is the DocRouter MCP Server?

The DocRouter MCP Server is a TypeScript-based server that implements the Model Context Protocol, allowing AI applications like Claude Desktop, Cursor IDE, and other MCP-compatible tools to interact with DocRouter's API for:

- Document management and retrieval
- OCR text extraction
- AI-powered data extraction using prompts
- Schema and form management
- Tag and prompt management
- LLM chat capabilities
- Search functionality

## Installation Methods

### Method 1: Global Installation (Recommended)

Install the package globally to make the `docrouter-mcp` binary available system-wide:

```bash
npm install -g @docrouter/mcp
```

After installation, verify the binary is available:

```bash
which docrouter-mcp
# Should output: /path/to/node/bin/docrouter-mcp

# Test the installation
docrouter-mcp --help
```

### Method 2: Local Installation

Install the package locally in your project:

```bash
npm install @docrouter/mcp
```

This method requires you to reference the full path to the executable in your MCP configuration.

## Prerequisites

Before setting up the MCP server, ensure you have:

1. **Node.js 18+** installed on your system
2. **DocRouter Account** with API access
3. **DocRouter Credentials**:
   - Organization API Token (`DOCROUTER_ORG_API_TOKEN`) - **Required**
   - API URL (optional, defaults to `https://app.docrouter.ai/fastapi`)

**Note**: The organization ID is automatically resolved from the API token, so you don't need to provide it separately.

## Configuration

### Environment Variables

The MCP server can be configured using environment variables:

```bash
export DOCROUTER_API_URL="https://app.docrouter.ai/fastapi"
export DOCROUTER_ORG_API_TOKEN="your-org-api-token"
```

**Important**: Only the organization API token is required. The organization ID is automatically resolved from the token.

### MCP Configuration Files

The configuration depends on which AI application you're using:

#### For Cursor IDE

Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "docrouter": {
      "command": "docrouter-mcp",
      "env": {
        "DOCROUTER_API_URL": "https://app.docrouter.ai/fastapi",
        "DOCROUTER_ORG_API_TOKEN": "your-org-api-token"
      }
    }
  }
}
```

#### For Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "docrouter": {
      "command": "docrouter-mcp",
      "env": {
        "DOCROUTER_API_URL": "https://app.docrouter.ai/fastapi",
        "DOCROUTER_ORG_API_TOKEN": "your-org-api-token"
      }
    }
  }
}
```

#### For Local Installation

If you installed locally, use the full path:

```json
{
  "mcpServers": {
    "docrouter": {
      "command": "node",
      "args": ["node_modules/@docrouter/mcp/dist/index.js"],
      "env": {
        "DOCROUTER_API_URL": "https://app.docrouter.ai/fastapi",
        "DOCROUTER_ORG_API_TOKEN": "your-org-api-token"
      }
    }
  }
}
```

### Command Line Arguments

You can also configure the server using command line arguments:

```bash
docrouter-mcp --url "https://app.docrouter.ai/fastapi" --org-token "your-org-api-token" --timeout 30000 --retries 3
```

Available arguments:
- `--url <URL>` - DocRouter API base URL (default: `https://app.docrouter.ai/fastapi`)
- `--org-token <TOKEN>` - DocRouter organization API token (required)
- `--timeout <MS>` - Request timeout in milliseconds (default: 30000)
- `--retries <COUNT>` - Number of retry attempts (default: 3)
- `--tools` - List all supported MCP tools
- `--claude-md` - Print CLAUDE.md contents
- `-h, --help` - Show help message

## Step-by-Step Setup

### 1. Install the Package

```bash
# Global installation (recommended)
npm install -g @docrouter/mcp

# Or local installation
npm install @docrouter/mcp
```

### 2. Verify Installation

```bash
# Check if binary is available (global install)
which docrouter-mcp

# Or check package installation (local install)
npm list @docrouter/mcp

# Test the server
docrouter-mcp --help
```

### 3. Create Configuration File

For **Cursor IDE**, create `.mcp.json`:

```bash
touch .mcp.json
```

### 4. Add Configuration

Copy the appropriate configuration from above and replace:
- `your-org-api-token` with your actual DocRouter organization API token
- `https://app.docrouter.ai/fastapi` with your API URL (if different)

**Note**: The organization ID is automatically resolved from the token, so you don't need to provide it.

### 5. Test the Configuration

Test the MCP server manually:

```bash
# Set environment variables
export DOCROUTER_ORG_API_TOKEN="your-org-api-token"

# Run the server directly
docrouter-mcp
```

## Available MCP Tools

Once configured, the following tools become available in your AI application:

### Document Management

- `upload_documents(documents)` - Upload documents from file paths
  - `documents`: Array of objects with `file_path` (required), `name` (optional), `tag_ids` (optional), `metadata` (optional)
- `list_documents(skip, limit, tagIds, nameSearch, metadataSearch)` - List documents with optional filters
- `get_document(documentId, fileType, save_path)` - Get document metadata and optionally download file
  - `fileType`: "original" or "pdf" (default: "original")
  - `save_path`: Optional file path or directory to save the document
- `update_document(documentId, documentName, tagIds, metadata)` - Update document metadata
- `delete_document(documentId)` - Delete a document

### OCR Operations

- `get_ocr_blocks(documentId)` - Get OCR blocks with position and text information
- `get_ocr_text(documentId, pageNum)` - Get OCR text (optionally for a specific page)
- `get_ocr_metadata(documentId)` - Get OCR metadata (n_pages, ocr_date)

### LLM Operations

- `run_llm(documentId, promptRevId, force)` - Run AI extraction on a document
  - `force`: Whether to force re-extraction (default: false)
- `get_llm_result(documentId, promptRevId, fallback)` - Get LLM extraction results
  - `fallback`: Use fallback results if current not found (default: false)
- `update_llm_result(documentId, promptId, result, isVerified)` - Update LLM extraction results
- `delete_llm_result(documentId, promptId)` - Delete LLM extraction results
- `run_llm_chat(messages, model, temperature, max_tokens, stream)` - Run LLM chat
  - `messages`: Array of message objects with `role` ("system", "user", "assistant") and `content`
  - `model`: Model to use
  - `temperature`, `max_tokens`, `stream`: Optional parameters

### Tag Management

- `create_tag(tag)` - Create a new tag
  - `tag`: Object with `name` (required), `color` (required)
- `get_tag(tagId)` - Get tag by ID
- `list_tags(skip, limit, nameSearch)` - List tags with optional search
- `update_tag(tagId, tag)` - Update a tag
- `delete_tag(tagId)` - Delete a tag

### Prompt Management

- `create_prompt(prompt)` - Create a new prompt
  - `prompt`: Object with `name` (required), `content` (required)
- `list_prompts(skip, limit, document_id, tag_ids, nameSearch)` - List prompts with optional filters
- `get_prompt(promptRevId)` - Get prompt by revision ID
- `update_prompt(promptId, content, model, schema_id, tag_ids)` - Update a prompt
  - All parameters except `promptId` are optional
- `delete_prompt(promptId)` - Delete a prompt

### Schema Management

- `create_schema(name, response_format)` - Create a new schema
- `list_schemas(skip, limit, nameSearch)` - List schemas with optional search
- `get_schema(schemaRevId)` - Get schema by revision ID
- `update_schema(schemaId, schema)` - Update a schema
- `delete_schema(schemaId)` - Delete a schema
- `validate_against_schema(schemaRevId, data)` - Validate data against a schema
- `validate_schema(schema)` - Validate schema format for correctness (takes JSON string)

### Form Management

- `create_form(name, response_format)` - Create a new form
- `list_forms(skip, limit, tag_ids)` - List forms with optional tag filter
- `get_form(formRevId)` - Get form by revision ID
- `update_form(formId, form)` - Update a form
- `delete_form(formId)` - Delete a form
- `submit_form(documentId, formRevId, submission_data, submitted_by)` - Submit a form
- `get_form_submission(documentId, formRevId)` - Get form submission
- `delete_form_submission(documentId, formRevId)` - Delete form submission
- `validate_form(form)` - Validate Form.io form format for correctness (takes JSON string)

### Organization and Models

- `get_organization()` - Get information about the current organization (name, type, ID)
- `list_llm_models()` - List enabled LLM models available for use in prompts

### Help and Guidance

- `help()` - Get general API help information
- `help_prompts()` - Get detailed help on creating and configuring prompts
- `help_schemas()` - Get detailed help on creating and configuring schemas
- `help_forms()` - Get detailed help on creating and configuring forms

## Example Workflows

### 1. Document Analysis Workflow

```typescript
// List documents with filters
const documents = await list_documents({
  skip: 0,
  limit: 10,
  nameSearch: "invoice",
  tagIds: "tag1,tag2"
});

// Get OCR text for the first document
const ocrText = await get_ocr_text({
  documentId: documents.documents[0].id
});

// List available prompts
const prompts = await list_prompts({
  nameSearch: "invoice"
});

// Run extraction with a specific prompt
const extraction = await run_llm({
  documentId: documents.documents[0].id,
  promptRevId: prompts.prompts[0].prompt_revid,
  force: false
});

// Get extraction results
const result = await get_llm_result({
  documentId: documents.documents[0].id,
  promptRevId: prompts.prompts[0].prompt_revid
});
```

### 2. Document Upload and Processing Workflow

```typescript
// Upload documents from file paths
const uploadResult = await upload_documents({
  documents: [
    {
      file_path: "/path/to/invoice.pdf",
      name: "invoice.pdf",
      tag_ids: ["tag1", "tag2"],
      metadata: { category: "invoice" }
    }
  ]
});

const documentId = uploadResult.documents[0].document_id;

// Get document and save to disk
const document = await get_document({
  documentId: documentId,
  fileType: "pdf",
  save_path: "/path/to/downloads/"
});

// Get OCR text
const ocrText = await get_ocr_text({
  documentId: documentId
});
```

### 3. Schema and Prompt Creation Workflow

```typescript
// Validate schema format
const schemaValidation = await validate_schema({
  schema: JSON.stringify({
    type: "json_schema",
    json_schema: {
      name: "invoice_extraction",
      schema: {
        type: "object",
        properties: {
          invoice_date: { type: "string", description: "invoice date" }
        },
        required: ["invoice_date"],
        additionalProperties: false
      },
      strict: true
    }
  })
});

// Create schema if valid
if (schemaValidation.valid) {
  const schema = await create_schema({
    name: "Invoice Schema",
    response_format: {
      type: "json_schema",
      json_schema: {
        name: "invoice_extraction",
        schema: {
          type: "object",
          properties: {
            invoice_date: { type: "string", description: "invoice date" }
          },
          required: ["invoice_date"],
          additionalProperties: false
        },
        strict: true
      }
    }
  });

  // Create prompt linked to schema
  const prompt = await create_prompt({
    prompt: {
      name: "Invoice Extractor",
      content: "Extract invoice information from the document."
    }
  });

  // Update prompt to link schema
  await update_prompt({
    promptId: prompt.prompt_id,
    schema_id: schema.schema_id
  });
}
```

### 4. Form Management Workflow

```typescript
// Validate form format
const formValidation = await validate_form({
  form: JSON.stringify({
    json_formio: [
      {
        type: "textfield",
        key: "invoice_number",
        label: "Invoice Number",
        input: true
      }
    ]
  })
});

// Create form if valid
if (formValidation.valid) {
  const form = await create_form({
    name: "Invoice Form",
    response_format: {
      type: "formio",
      formio: {
        json_formio: [
          {
            type: "textfield",
            key: "invoice_number",
            label: "Invoice Number",
            input: true
          }
        ]
      }
    }
  });

  // Submit form for a document
  await submit_form({
    documentId: "document_id",
    formRevId: form.form_revid,
    submission_data: {
      invoice_number: "INV-123"
    },
    submitted_by: "user@example.com"
  });
}
```

## Troubleshooting

### Common Issues

#### 1. "MCP server not connecting"

**Solutions:**
- Verify the binary exists: `which docrouter-mcp`
- Check configuration syntax in your `.mcp.json`
- Ensure environment variables are set correctly
- Test the server manually: `docrouter-mcp`
- Verify the organization API token is valid

#### 2. "Command not found"

**Solutions:**
- Reinstall globally: `npm install -g @docrouter/mcp`
- Check your PATH: `echo $PATH`
- Use full path in configuration if needed
- For local install, use: `node node_modules/@docrouter/mcp/dist/index.js`

#### 3. "Failed to resolve organization ID from token"

**Solutions:**
- Verify you're using an organization API token (not an account-level token)
- Check that the token is valid and not expired
- Ensure the token has the correct permissions
- Test API access with your credentials independently

#### 4. "Environment variables not set"

**Solutions:**
- Verify variable names: `DOCROUTER_ORG_API_TOKEN` (not `DOCROUTER_ORG_ID`)
- Check variable values are correct and not expired
- Test API access with your credentials
- Note: Organization ID is automatically resolved from token

#### 5. "Permission denied"

**Solutions:**
- Don't use `sudo` for MCP servers
- Check file permissions on the binary
- Ensure you have access to the project directory

### Debug Mode

Enable debug logging by adding to your environment:

```json
{
  "mcpServers": {
    "docrouter": {
      "command": "docrouter-mcp",
      "env": {
        "DOCROUTER_API_URL": "https://app.docrouter.ai/fastapi",
        "DOCROUTER_ORG_API_TOKEN": "your-org-api-token",
        "DEBUG": "mcp:*"
      }
    }
  }
}
```

### Verification Commands

```bash
# Check package installation
npm list -g @docrouter/mcp

# Check binary location
which docrouter-mcp

# Test server startup
docrouter-mcp --help

# List all available tools
docrouter-mcp --tools

# Verify environment variables
echo $DOCROUTER_ORG_API_TOKEN

# Test with command line arguments
docrouter-mcp --org-token "your-token" --url "https://app.docrouter.ai/fastapi"
```

## Security Best Practices

### Credential Management

1. **Never commit credentials** to version control
2. **Use environment variables** instead of hardcoded values
3. **Rotate API tokens** regularly
4. **Limit token permissions** to minimum required access
5. **Add `.mcp.json` to `.gitignore`** if it contains real credentials

### Example Secure Configuration

```bash
# Set environment variables in your shell profile
echo 'export DOCROUTER_ORG_API_TOKEN="your-token"' >> ~/.bashrc
source ~/.bashrc
```

Then use environment variables in your configuration:

```json
{
  "mcpServers": {
    "docrouter": {
      "command": "docrouter-mcp",
      "env": {
        "DOCROUTER_ORG_API_TOKEN": "${DOCROUTER_ORG_API_TOKEN}"
      }
    }
  }
}
```

## Advanced Configuration

### Custom API Endpoints

For development or custom deployments:

```json
{
  "mcpServers": {
    "docrouter": {
      "command": "docrouter-mcp",
      "env": {
        "DOCROUTER_API_URL": "http://localhost:8000",
        "DOCROUTER_ORG_API_TOKEN": "your-org-api-token"
      }
    }
  }
}
```

### Multiple Environments

You can configure multiple DocRouter instances:

```json
{
  "mcpServers": {
    "docrouter-prod": {
      "command": "docrouter-mcp",
      "env": {
        "DOCROUTER_API_URL": "https://app.docrouter.ai/fastapi",
        "DOCROUTER_ORG_API_TOKEN": "prod-token"
      }
    },
    "docrouter-dev": {
      "command": "docrouter-mcp",
      "env": {
        "DOCROUTER_API_URL": "http://localhost:8000",
        "DOCROUTER_ORG_API_TOKEN": "dev-token"
      }
    }
  }
}
```

### Custom Timeout and Retries

```json
{
  "mcpServers": {
    "docrouter": {
      "command": "docrouter-mcp",
      "args": ["--timeout", "60000", "--retries", "5"],
      "env": {
        "DOCROUTER_ORG_API_TOKEN": "your-org-api-token"
      }
    }
  }
}
```

## Package Information

- **Package Name**: `@docrouter/mcp`
- **Current Version**: 1.0.0
- **Server Version**: 0.1.0
- **Node.js Requirement**: >=18.0.0
- **License**: MIT
- **Repository**: https://github.com/analytiq/doc-router

### Package Contents

The published package includes:
- Built JavaScript files (CommonJS + ES Modules)
- TypeScript definitions
- Source maps for debugging
- Bundled knowledge base files (prompts.md, schemas.md, forms.md)
- Documentation

### Dependencies

- `@docrouter/sdk`: ^1.0.0
- `@modelcontextprotocol/sdk`: ^1.25.3
- `zod`: ^4.3.6

## Support and Resources

### Getting Help

1. **Check the troubleshooting section** above
2. **Review the README.md** in the package
3. **Test with debug mode** enabled
4. **Verify your DocRouter API access** independently
5. **Use the help tools**:
   - `help()` - General API help
   - `help_prompts()` - Prompt creation guide
   - `help_schemas()` - Schema creation guide
   - `help_forms()` - Form creation guide

### Package Management

```bash
# Update to latest version
npm update -g @docrouter/mcp

# Check current version
npm list -g @docrouter/mcp

# Uninstall if needed
npm uninstall -g @docrouter/mcp
```

### Development

For developers working on the MCP server:

```bash
# Clone the repository
git clone https://github.com/analytiq/doc-router
cd packages/typescript/mcp

# Install dependencies
npm install

# Build the project
npm run build

# Run tests
npm test

# Development mode
npm run dev

# Type checking
npm run type-check

# Linting
npm run lint
```

## Key Differences from Previous Versions

1. **Organization ID Resolution**: The organization ID is now automatically resolved from the API token. You no longer need to provide `DOCROUTER_ORG_ID` separately.

2. **Environment Variable Names**: 
   - Use `DOCROUTER_ORG_API_TOKEN` (not `DOCROUTER_ORG_API_TOKEN` with separate `DOCROUTER_ORG_ID`)
   - Use `DOCROUTER_API_URL` (not `DOCROUTER_URL`)

3. **New Tools**: Added support for:
   - Form management (create, list, get, update, delete, submit, validate)
   - Schema validation (`validate_schema`)
   - Form validation (`validate_form`)
   - LLM chat (`run_llm_chat`)
   - Organization info (`get_organization`)
   - LLM models listing (`list_llm_models`)

4. **Enhanced Document Operations**: 
   - `get_document` now supports file download with `save_path` parameter
   - `list_documents` supports `metadataSearch` parameter

5. **Improved Prompt Updates**: `update_prompt` now preserves existing fields when updating
