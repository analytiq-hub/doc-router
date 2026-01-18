# DocRouter Prompt Configuration Guide

## Overview

Prompts in DocRouter are instructions that guide AI language models to extract structured information from documents. A well-configured prompt ensures consistent, accurate data extraction across your document processing pipeline.

## Table of Contents

1. [What is a Prompt?](#what-is-a-prompt)
2. [Prompt Structure](#prompt-structure)
3. [Associating Schemas](#associating-schemas)
4. [Selecting Language Models](#selecting-language-models)
5. [Tagging and Organization](#tagging-and-organization)
6. [Best Practices](#best-practices)
7. [API Integration](#api-integration)
8. [Examples](#examples)

---

## What is a Prompt?

A prompt is a text instruction that tells an AI model what to do with a document. In DocRouter, prompts:

- Guide LLMs to extract specific data from documents
- Can be linked to schemas for structured output validation
- Can be tagged to automatically process specific document types
- Support multiple AI models (OpenAI, Anthropic Claude, Google Gemini, etc.)

---

## Prompt Structure

### Basic Components

Every prompt in DocRouter has the following components:

| Component | Required | Description |
|-----------|----------|-------------|
| **Name** | Yes | Human-readable identifier for the prompt |
| **Content** | Yes | The instruction text sent to the AI model |
| **Schema** | No | Optional JSON schema for structured output |
| **Model** | No | AI model to use (defaults to `gpt-4o-mini`) |
| **Tags** | No | Document tags that trigger this prompt |

### Prompt Content

The prompt content is the core instruction sent to the AI model. It should:

- Be clear and specific about what data to extract
- Provide context about the document type
- Include examples when helpful
- Reference the schema fields if one is associated

**Example:**
```
Extract key information from this invoice document.

Please identify:
- Invoice number
- Invoice date
- Vendor name and address
- Customer name
- Line items with quantities and prices
- Subtotal, tax, and total amounts
- Payment terms

Return the data in the format specified by the schema.
```

---

## Associating Schemas

### Why Use Schemas?

Linking a schema to a prompt ensures:

- **Structured output**: Data is returned in a consistent JSON format
- **Type validation**: Fields are validated against the schema
- **100% adherence**: With strict mode, the LLM output always matches the schema
- **No post-processing**: Output is immediately usable by your application

### How to Associate a Schema

When creating or editing a prompt, you can optionally select a schema from the dropdown menu. The system will:

1. Link the prompt to the schema's `schema_id`
2. Store the current `schema_version` for versioning
3. Use the latest version of the schema when processing documents
4. Display schema fields in the prompt editor for reference

### Schema Versioning

DocRouter maintains schema versions automatically:

- When you update a schema, a new version is created
- Existing prompts continue to reference their original schema version
- You can manually update prompts to use newer schema versions
- The `schema_revid` uniquely identifies each schema version

**Example Flow:**
1. Create a schema: "Invoice Extraction" (version 1)
2. Create a prompt linked to this schema
3. Update the schema to add new fields (version 2 created)
4. The prompt still uses version 1 until manually updated
5. Edit the prompt and it automatically uses version 2

---

## Selecting Language Models

### Listing Available Models

To see which LLM models are available for your organization, use the `list_llm_models` MCP tool:

```
list_llm_models()
```

This returns an array of enabled model names that can be used when creating or updating prompts. Only models that are enabled in your organization's LLM provider settings will be returned.

### Recommended Models for Document Processing

**For document extraction tasks:**
- **`gemini/gemini-3-flash-preview`** or other Gemini models - Excellent for document processing with great speed and cost efficiency
- **OpenAI models** (e.g., `gpt-4o-mini`, `gpt-4o`) - Reliable and well-suited for structured extraction
- **Grok models** - Good choice for document analysis and extraction

### Default Model

If no model is specified, DocRouter uses **`gpt-4o-mini`** as the default model.

### Model Configuration

AI model providers must be configured in your organization settings:

1. Navigate to Organization Settings → LLM Providers
2. Add API keys for the providers you want to use
3. Enable/disable specific models
4. Only enabled models are available for use in prompts

---

## Tagging and Organization

### What are Tags?

Tags are labels that help organize and route documents to the appropriate prompts. They enable:

- **Automatic processing**: Documents with matching tags trigger specific prompts
- **Organization**: Group related prompts and documents
- **Workflow automation**: Route documents based on type or category

### How Tags Work

1. **Create tags** in your organization (e.g., "invoice", "receipt", "contract")
2. **Assign tags to prompts** - Select one or more tags when creating a prompt
3. **Upload documents with tags** - Tag documents during upload or later
4. **Automatic execution** - When a document is uploaded with a tag, all prompts with that tag are automatically executed

### Tag-Based Routing Example

```
Tag: "invoice"
├── Prompt: "Invoice Data Extraction" (runs automatically)
├── Prompt: "Invoice Validation" (runs automatically)
└── Prompt: "Vendor Analysis" (runs automatically)

Tag: "receipt"
├── Prompt: "Receipt OCR Enhancement"
└── Prompt: "Expense Categorization"
```

### Multiple Tags

Prompts can have multiple tags:

- A document with tags ["invoice", "urgent"] will trigger:
  - All prompts tagged "invoice"
  - All prompts tagged "urgent"
  - All prompts tagged both "invoice" AND "urgent"

---

## Best Practices

### 1. Write Clear, Specific Prompts

**Good:**
```
Extract all line items from this invoice. For each line item, capture:
- Item description or product name
- Quantity (numeric value only)
- Unit price (include currency symbol)
- Line total

Format: Return as a JSON array matching the schema.
```

**Avoid:**
```
Get the items from the invoice.
```

### 2. Reference the Schema in Your Prompt

When using a schema, mention it in your prompt:

```
Extract invoice data according to the provided schema.

Focus on accuracy for:
- invoice_number: Must be exact
- invoice_date: Use YYYY-MM-DD format
- line_items: Include all items, even if partially visible
- total_amount: Include currency symbol

Return empty strings for fields not found in the document.
```

### 3. Choose the Right Model for the Task

Use `list_llm_models()` to see available models, then select based on your needs:
- **Document processing**: Prefer Gemini models (e.g., `gemini/gemini-3-flash-preview`) or OpenAI/Grok models
- **Complex reasoning**: Use higher-capability models when needed
- **High volume**: Gemini Flash models offer excellent speed and cost efficiency

### 4. Use Tags Strategically

- Create tags that represent document types: "invoice", "receipt", "po", "contract"
- Use tags for workflow stages: "pending", "reviewed", "approved"
- Combine tags for conditional processing: ["invoice", "international"]

### 5. Test and Iterate

- Start with a simple prompt and test on sample documents
- Review extraction results and refine the prompt
- Add specific instructions for edge cases
- Update the schema if you discover new fields to extract

### 6. Version Control

- Update prompt names to indicate major changes: "Invoice Extraction v2"
- Document what changed in prompt content
- Test new versions before replacing production prompts
- Keep old prompt versions for comparison

---

## API Integration

DocRouter provides multiple ways to interact with prompts programmatically:

- **TypeScript/JavaScript SDK** - Type-safe client library for Node.js and browsers (see `packages/typescript/sdk/`)
- **Python SDK** - Type-safe Python client library (see `packages/python/sdk/`)
- **REST API** - Direct HTTP requests (see API documentation for endpoints)
- **MCP (Model Context Protocol)** - Integration with AI assistants like Claude Code

All methods support the same prompt operations: create, list, retrieve, update, and delete prompts.

### MCP Tool Examples

#### list_llm_models

Before creating or updating a prompt, check which LLM models are available for your organization:

```
list_llm_models()
```

**Returns:** Object with `models` array containing enabled model names (e.g., `["gpt-4o-mini", "gemini/gemini-3-flash-preview", "gpt-4o", ...]`)

#### create_prompt

Creates a new prompt. Requires `name` and `content` parameters.

```
create_prompt(
  prompt: {
    "name": "Invoice Extraction",
    "content": "Extract the following from this invoice: invoice number, date, vendor, total amount.",
    "model": "gemini/gemini-3-flash-preview",  # Optional, defaults to gpt-4o-mini
    "schema_id": "abc123",  # Optional, link to a schema
    "tag_ids": ["tag1", "tag2"]  # Optional, tags that trigger this prompt
  }
)
```

**Parameters:**
- `prompt` (object, required): Prompt configuration containing:
  - `name` (string, required): Human-readable name for the prompt
  - `content` (string, required): The prompt instruction text
  - `model` (string, optional): LLM model to use (defaults to `gpt-4o-mini`)
  - `schema_id` (string, optional): Schema ID to link for structured output
  - `tag_ids` (array of strings, optional): Tag IDs that trigger this prompt

**Returns:** Created prompt object with `prompt_id`, `prompt_revid`, and `prompt_version`

#### list_prompts

Lists all prompts with optional filtering.

```
list_prompts(skip: 0, limit: 10, nameSearch: "Invoice", tag_ids: "tag1,tag2")
```

**Parameters:**
- `skip` (number, optional): Number of prompts to skip (default: 0)
- `limit` (number, optional): Number of prompts to return (default: 10)
- `document_id` (string, optional): Filter prompts by document ID
- `tag_ids` (string, optional): Comma-separated tag IDs to filter by
- `nameSearch` (string, optional): Search prompts by name

**Returns:** Object with `prompts` array and `total_count`

#### get_prompt

Retrieves a specific prompt by its revision ID.

```
get_prompt(promptRevId: "696c4a89fc1c7a2d00322b95")
```

**Parameters:**
- `promptRevId` (string, required): The prompt revision ID

**Returns:** Full prompt object including `name`, `content`, `model`, `schema_id`, `tag_ids`, `prompt_id`, `prompt_revid`, `prompt_version`

#### update_prompt

Updates a prompt. You can update the content, model, schema_id, or tag_ids. Fields not provided will be preserved from the current prompt.

```
# Update only the content
update_prompt(
  promptId: "696c4a89fc1c7a2d00322b95",
  content: "Extract the following from this invoice: invoice number, date, vendor name, customer name, line items, and total amount. Return data according to the schema."
)

# Update only the model
update_prompt(
  promptId: "696c4a89fc1c7a2d00322b95",
  model: "gemini/gemini-3-flash-preview"
)

# Update multiple fields
update_prompt(
  promptId: "696c4a89fc1c7a2d00322b95",
  content: "Updated extraction instructions...",
  model: "gemini/gemini-3-flash-preview",
  tag_ids: ["invoice", "urgent"]
)
```

**Parameters:**
- `promptId` (string, required): The prompt ID (not revision ID) to update
- `content` (string, optional): The updated prompt content (if omitted, current content is preserved)
- `model` (string, optional): LLM model to use (if omitted, current model is preserved)
- `schema_id` (string, optional): Schema ID to link (if omitted, current schema_id is preserved)
- `tag_ids` (array of strings, optional): Tag IDs that trigger this prompt (if omitted, current tag_ids are preserved)

**Returns:** Updated prompt object with new `prompt_revid` and incremented `prompt_version`

#### delete_prompt

Deletes a prompt and all its versions.

```
delete_prompt(promptId: "696c4a89fc1c7a2d00322b95")
```

**Parameters:**
- `promptId` (string, required): The prompt ID to delete

**Returns:** Confirmation of deletion

### Common Workflow

```
# 1. Check available LLM models
list_llm_models()
# Returns: { "models": ["gpt-4o-mini", "gemini/gemini-3-flash-preview", "gpt-4o"] }

# 2. Create a new prompt
create_prompt(
  prompt: {
    "name": "Invoice Extraction",
    "content": "Extract invoice data...",
    "model": "gemini/gemini-3-flash-preview",
    "schema_id": "abc123",
    "tag_ids": ["invoice"]
  }
)
# Returns: { prompt_id: "xyz789", prompt_revid: "xyz789", prompt_version: 1, ... }

# 3. List prompts to find the one you need
list_prompts(nameSearch: "Invoice")
# Returns: { prompts: [...], total_count: 1 }

# 4. Get full prompt details
get_prompt(promptRevId: "xyz789")
# Returns: Full prompt object

# 5. Update the prompt content
update_prompt(promptId: "xyz789", content: "Updated extraction instructions...")
# Returns: { prompt_id: "xyz789", prompt_revid: "def456", prompt_version: 2, ... }

# 6. Delete the prompt when no longer needed
delete_prompt(promptId: "xyz789")
# Returns: Deletion confirmation
```

---

## Examples

### Example 1: Simple Invoice Extraction

**Prompt Name:** Invoice Basic Info

**Content:**
```
Extract the following information from this invoice:

1. Invoice number
2. Invoice date
3. Vendor/supplier name
4. Customer/buyer name
5. Total amount due

If any information is not found, return an empty string for that field.
```

**Schema:** None (unstructured extraction)

**Model:** `gpt-4o-mini` (default)

**Tags:** ["invoice"]

---

### Example 2: Structured Receipt Processing

**Prompt Name:** Receipt Data Extraction

**Content:**
```
You are processing a receipt document. Extract all transaction details with high accuracy.

Required fields:
- Merchant name and address
- Transaction date and time
- All purchased items with prices
- Subtotal, tax breakdown, and total
- Payment method

Return the data in strict adherence to the provided JSON schema. Use empty strings for missing data.
```

**Schema:** "Receipt Schema" (structured output with line items array)

**Model:** Default (`gpt-4o-mini`) or higher-capability model for complex documents

**Tags:** ["receipt", "expense"]

---

### Example 3: Contract Analysis

**Prompt Name:** Contract Key Terms

**Content:**
```
Analyze this contract and extract key terms and conditions.

Focus on:
- Party names (all parties involved)
- Contract effective date and expiration date
- Contract value or payment terms
- Key obligations of each party
- Termination clauses
- Jurisdiction and governing law

For each extracted element, note the page number where found.
Summarize any unusual or non-standard clauses.
```

**Schema:** "Contract Schema" (complex nested structure)

**Model:** Higher-capability model (e.g., Claude Sonnet 4) recommended for complex reasoning

**Tags:** ["contract", "legal"]

---

### Example 4: Resume Parsing

**Prompt Name:** Resume Information Extraction

**Content:**
```
Extract candidate information from this resume/CV.

Personal Information:
- Full name
- Email address
- Phone number
- Location (city/country)

Professional Summary:
- Current or most recent position
- Years of experience
- Key skills (programming languages, tools, frameworks)

Education:
- Degrees earned
- Institutions attended
- Graduation years

Work Experience:
- Company names
- Job titles
- Employment dates
- Key responsibilities

Format all data according to the provided schema. Use empty strings where information is not available.
```

**Schema:** "Resume Schema"

**Model:** `gemini/gemini-2.0-flash` or default (`gpt-4o-mini`)

**Tags:** ["resume", "hr", "candidate"]

---

## Prompt Workflow

### 1. Design Phase
- Identify what data needs to be extracted
- Determine if a schema is needed for structured output
- Choose the appropriate AI model based on complexity
- Plan which tags should trigger this prompt

### 2. Creation Phase
- Write clear, specific prompt instructions
- Associate with a schema if structured output is needed
- Select the AI model
- Add relevant tags for automatic processing

### 3. Testing Phase
- Upload sample documents with appropriate tags
- Review extraction results
- Refine prompt wording and instructions
- Adjust schema if fields are missing or incorrect

### 4. Production Phase
- Tag incoming documents to trigger prompt execution
- Monitor extraction quality and accuracy
- Update prompts as document formats evolve
- Version prompts when making significant changes

---

## Troubleshooting

### Common Issues

**Issue:** LLM returns empty or incorrect data
- **Solution:** Make prompt more specific, provide examples, or use a more capable model

**Issue:** Output doesn't match schema
- **Solution:** Verify strict mode is enabled, mention schema in prompt content

**Issue:** Prompt not triggered automatically
- **Solution:** Check that document tags match prompt tags exactly

**Issue:** Slow extraction performance
- **Solution:** Switch to a faster model like `gemini/gemini-2.0-flash`

**Issue:** Inconsistent results across documents
- **Solution:** Add more specific instructions, provide format examples and counter-examples, or switch to a higher-capability models

---

## Version Control

DocRouter maintains prompt versioning:

- Each prompt update creates a new version
- `prompt_version` increments with each change
- `prompt_revid` uniquely identifies each version
- Previous versions remain accessible for historical processing

---

## References

- [Schema Definition Manual](./schemas.md)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [DocRouter API Documentation](../README.md)

---

**Document Version:** 1.0
**Last Updated:** 2025-01-11
**Maintained by:** DocRouter Development Team
