# DocRouter MCP Server Installation and Setup Guide

## Overview

The DocRouter MCP (Model Context Protocol) Server provides AI applications with seamless access to DocRouter's document processing capabilities. This guide covers everything you need to know to install, configure, and use the DocRouter MCP server.

## What is the DocRouter MCP Server?

The DocRouter MCP Server is a TypeScript-based server that implements the Model Context Protocol, allowing AI applications like Claude Desktop, Cursor IDE, and other MCP-compatible tools to interact with DocRouter's API for:

- Document management and retrieval
- OCR text extraction
- AI-powered data extraction using prompts
- Tag and prompt management
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
   - Organization ID (`DOCROUTER_ORG_ID`)
   - Organization API Token (`DOCROUTER_ORG_API_TOKEN`)
   - API URL (optional, defaults to production)

## Configuration

### Environment Variables

The MCP server can be configured using environment variables:

```bash
export DOCROUTER_API_URL="https://app.docrouter.ai/fastapi"
export DOCROUTER_ORG_ID="your-org-id"
export DOCROUTER_ORG_API_TOKEN="your-api-token"
```

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
        "DOCROUTER_ORG_ID": "your-org-id",
        "DOCROUTER_ORG_API_TOKEN": "your-api-token"
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
        "DOCROUTER_ORG_ID": "your-org-id",
        "DOCROUTER_ORG_API_TOKEN": "your-api-token"
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
        "DOCROUTER_ORG_ID": "your-org-id",
        "DOCROUTER_ORG_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

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
```

### 3. Create Configuration File

For **Cursor IDE**, create `.mcp.json`:

```bash
touch .mcp.json
```

### 4. Add Configuration

Copy the appropriate configuration from above and replace:
- `your-org-id` with your actual DocRouter organization ID
- `your-api-token` with your actual DocRouter API token
- `https://app.docrouter.ai/fastapi` with your API URL (if different)

### 5. Test the Configuration

Test the MCP server manually:

```bash
# Set environment variables
export DOCROUTER_ORG_ID="your-org-id"
export DOCROUTER_ORG_API_TOKEN="your-api-token"

# Run the server directly
docrouter-mcp
```

## Available MCP Tools

Once configured, the following tools become available in your AI application:

### Document Management
- `get_docrouter_documents()` - List all documents
- `get_docrouter_document(documentId)` - Get document by ID
- `get_docrouter_document_ocr(documentId)` - Get raw OCR text
- `get_docrouter_document_ocr_metadata(documentId)` - Get OCR metadata

### Data Extraction
- `run_docrouter_extraction(documentId, promptRevId, force)` - Run AI extraction
- `get_docrouter_extraction(documentId, promptRevId)` - Get extraction results

### Search and Discovery
- `search_docrouter_documents(query, tagIds)` - Search documents
- `search_docrouter_prompts(query)` - Search prompts
- `search_docrouter_tags(query)` - Search tags

### Management
- `get_docrouter_prompts()` - List all prompts
- `get_docrouter_prompt(promptRevId)` - Get prompt by ID
- `get_docrouter_tags()` - List all tags
- `get_docrouter_tag(tagId)` - Get tag by ID

### Help and Guidance
- `docrouter_help()` - Get help information
- `docrouter_document_analysis_guide(documentId)` - Generate analysis guide

## Example Workflows

### 1. Document Analysis Workflow

```typescript
// Search for invoice documents
const documents = await search_docrouter_documents("invoice");

// Get OCR text for the first document
const ocrText = await get_docrouter_document_ocr(documents.documents[0].id);

// Find available prompts for invoice processing
const prompts = await search_docrouter_prompts("invoice");

// Run extraction with a specific prompt
const extraction = await run_docrouter_extraction(
  documents.documents[0].id, 
  prompts.prompts[0].id
);
```

### 2. Document Discovery Workflow

```typescript
// Get all documents
const allDocuments = await get_docrouter_documents();

// Get all available prompts
const allPrompts = await get_docrouter_prompts();

// Get all tags for categorization
const allTags = await get_docrouter_tags();
```

### 3. Guided Analysis Workflow

```typescript
// Get a step-by-step guide for analyzing a specific document
const guide = await docrouter_document_analysis_guide("document-id");

// Follow the guide to analyze the document
// The guide will provide specific prompts and extraction strategies
```

## Troubleshooting

### Common Issues

#### 1. "MCP server not connecting"

**Solutions:**
- Verify the binary exists: `which docrouter-mcp`
- Check configuration syntax in your `.mcp.json`
- Ensure environment variables are set correctly
- Test the server manually: `docrouter-mcp`

#### 2. "Command not found"

**Solutions:**
- Reinstall globally: `npm install -g @docrouter/mcp`
- Check your PATH: `echo $PATH`
- Use full path in configuration if needed

#### 3. "Environment variables not set"

**Solutions:**
- Verify variable names: `DOCROUTER_ORG_ID`, `DOCROUTER_ORG_API_TOKEN`
- Check variable values are correct and not expired
- Test API access with your credentials

#### 4. "Permission denied"

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
        "DOCROUTER_ORG_ID": "your-org-id",
        "DOCROUTER_ORG_API_TOKEN": "your-api-token",
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

# Verify environment variables
echo $DOCROUTER_ORG_ID
echo $DOCROUTER_ORG_API_TOKEN
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
echo 'export DOCROUTER_ORG_ID="your-org-id"' >> ~/.bashrc
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
        "DOCROUTER_ORG_ID": "${DOCROUTER_ORG_ID}",
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
        "DOCROUTER_ORG_ID": "your-org-id",
        "DOCROUTER_ORG_API_TOKEN": "your-token"
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
        "DOCROUTER_ORG_ID": "prod-org-id",
        "DOCROUTER_ORG_API_TOKEN": "prod-token"
      }
    },
    "docrouter-dev": {
      "command": "docrouter-mcp",
      "env": {
        "DOCROUTER_API_URL": "http://localhost:8000",
        "DOCROUTER_ORG_ID": "dev-org-id",
        "DOCROUTER_ORG_API_TOKEN": "dev-token"
      }
    }
  }
}
```

## Package Information

- **Package Name**: `@docrouter/mcp`
- **Current Version**: 0.1.0
- **Node.js Requirement**: >=18.0.0
- **License**: MIT
- **Repository**: Available on npm registry

### Package Contents

The published package includes:
- Built JavaScript files (CommonJS + ES Modules)
- TypeScript definitions
- Source maps for debugging
- Bundled knowledge base files
- Documentation

## Support and Resources

### Getting Help

1. **Check the troubleshooting section** above
2. **Review the README.md** in the package
3. **Test with debug mode** enabled
4. **Verify your DocRouter API access** independently

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
git clone <repository-url>
cd packages/typescript/mcp

# Install dependencies
npm install

# Build the project
npm run build

# Run tests
npm test

# Development mode
npm run dev
```
