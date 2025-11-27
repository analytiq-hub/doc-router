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
| **Model** | No | AI model to use (defaults to `gemini-2.0-flash`) |
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

### Available Models

DocRouter supports multiple AI providers through LiteLLM, including:

- **OpenAI** - GPT-4, GPT-4o models
- **Anthropic** - Claude 3.5, Claude 4 Sonnet and Opus models
- **Google Gemini** - Gemini 2.0 and 2.5 Flash and Pro models
- **Groq** - DeepSeek and Llama models with ultra-fast inference
- **Mistral** - Mistral models
- **xAI** - Grok models
- **AWS Bedrock** - Claude models via AWS infrastructure
- **Azure OpenAI / Azure AI Studio** - Available when configured
- **Google Vertex AI** - Gemini models via Google Cloud

**For the complete and up-to-date list of supported models**, see `packages/analytiq_data/llm/providers.py` in the codebase. This file defines all available LLM providers and their specific model identifiers.

### Default Model

If no model is specified, DocRouter uses **`gpt-4o-mini`** as the default model.

### How to Choose a Model

When creating or editing a prompt, select a model from the dropdown. Consider:

**For general document extraction:**
- **`gpt-4o-mini`** (default) - Fast, cost-effective, and reliable for most use cases
- **`gemini/gemini-2.0-flash`** - Excellent option for extraction tasks with great speed/cost ratio

**For complex or challenging documents:**
- Use higher-capability models like Claude Sonnet 4 or GPT-5 for documents requiring advanced reasoning

**For chain-of-thought applications:**
- **Grok models** are particularly well-suited for applications requiring step-by-step reasoning and chain-of-thought processing

**For high-volume processing:**
- Gemini Flash models offer excellent speed and cost efficiency
- Groq models provide ultra-fast inference for time-sensitive applications

### Model Configuration

AI model providers must be configured in your organization settings:

1. Navigate to Organization Settings → LLM Providers
2. Add API keys for the providers you want to use
3. Enable/disable specific models
4. Only enabled models appear in the prompt editor

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

- **Complex documents**: Use Claude 3.5 Sonnet or GPT-4 Turbo
- **High volume**: Use Gemini 2.0 Flash for speed
- **Budget-conscious**: Use Claude 3 Haiku or Gemini Flash
- **Consistency needed**: Test multiple models and pick the best performer

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

- **TypeScript/JavaScript SDK** - Type-safe client library for Node.js and browsers (see `packages/typescript/docrouter-sdk/`)
- **Python SDK** - Type-safe Python client library (see `packages/python/sdk/`)
- **REST API** - Direct HTTP requests (see API documentation for endpoints)
- **MCP (Model Context Protocol)** - Integration with AI assistants like Claude Code

All methods support the same prompt operations: create, list, retrieve, update, and delete prompts.

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
