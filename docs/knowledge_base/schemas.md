# DocRouter Schema Definition Manual

## Overview

DocRouter uses **OpenAI's Structured Outputs JSON Schema format** to define extraction schemas for document processing. Schemas ensure that AI-extracted data from documents follows a consistent, validated structure.

## Table of Contents

1. [Schema Format Specification](#schema-format-specification)
2. [Basic Schema Structure](#basic-schema-structure)
3. [Field Types](#field-types)
4. [Required Fields and Strict Mode](#required-fields-and-strict-mode)
5. [Advanced Schema Features](#advanced-schema-features)
6. [Best Practices](#best-practices)
7. [Examples](#examples)
8. [API Integration](#api-integration)

---

## Schema Format Specification

### Root Structure

All DocRouter schemas follow this format:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "document_extraction",
    "schema": {
      "type": "object",
      "properties": { ... },
      "required": [ ... ],
      "additionalProperties": false
    },
    "strict": true
  }
}
```

### Components

| Component | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | Yes | Must be `"json_schema"` |
| `json_schema` | object | Yes | Container for schema definition |
| `json_schema.name` | string | Yes | Identifier for the schema (typically `"document_extraction"`) |
| `json_schema.schema` | object | Yes | JSON Schema specification following JSON Schema Draft 7 |
| `json_schema.strict` | boolean | Yes | **Must be `true`** - Ensures 100% schema adherence |

### Strict Mode Constraints

When `strict: true` is enabled (mandatory for DocRouter), the following rules apply:

1. **All properties MUST be in the `required` array** - No optional fields allowed
2. **`additionalProperties: false` MUST be set** - At every level, including nested objects
3. **Perfect schema adherence** - The LLM output will always match the schema exactly
4. **Default values for missing data** - Empty strings, zeros, false, or empty arrays/objects

---

## Basic Schema Structure

### Minimal Schema Example

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "document_extraction",
    "schema": {
      "type": "object",
      "properties": {
        "field_name": {
          "type": "string",
          "description": "Human-readable description of this field"
        }
      },
      "required": ["field_name"],
      "additionalProperties": false
    },
    "strict": true
  }
}
```

### Schema Object Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `type` | string | Yes | Must be `"object"` for root schema |
| `properties` | object | Yes | Defines all extractable fields |
| `required` | array | Yes | **Must list ALL properties** when `strict: true` |
| `additionalProperties` | boolean | Yes | **Must be `false`** when `strict: true` |

---

## Field Types

DocRouter schemas support standard JSON Schema data types:

### String Fields

```json
{
  "field_name": {
    "type": "string",
    "description": "A text field"
  }
}
```

**Use for:** Names, emails, addresses, free-text descriptions, comma-separated lists

### Number Fields

```json
{
  "amount": {
    "type": "number",
    "description": "A numeric value"
  }
}
```

**Use for:** Quantities, amounts, percentages, measurements

### Integer Fields

```json
{
  "count": {
    "type": "integer",
    "description": "A whole number"
  }
}
```

**Use for:** Counts, years, age, quantity of items

### Boolean Fields

```json
{
  "is_verified": {
    "type": "boolean",
    "description": "True/false indicator"
  }
}
```

**Use for:** Yes/no questions, checkboxes, status flags

### Array Fields

```json
{
  "skills": {
    "type": "array",
    "description": "List of programming skills",
    "items": {
      "type": "string"
    }
  }
}
```

**Use for:** Lists, multiple values, repeated items

### Object Fields (Nested)

```json
{
  "address": {
    "type": "object",
    "description": "Address information",
    "properties": {
      "street": {
        "type": "string",
        "description": "Street address"
      },
      "city": {
        "type": "string",
        "description": "City name"
      },
      "postal_code": {
        "type": "string",
        "description": "Postal code"
      }
    },
    "required": ["street", "city", "postal_code"],
    "additionalProperties": false
  }
}
```

**Use for:** Grouped related fields, structured sub-data

---

## Required Fields and Strict Mode

### Strict Mode Requirements

**IMPORTANT:** When using OpenAI's Structured Outputs with `strict: true` (which DocRouter uses), **ALL properties MUST be listed in the `required` array**. This is a mandatory requirement from OpenAI's API.

```json
{
  "type": "object",
  "properties": {
    "name": { "type": "string", "description": "Full name" },
    "email": { "type": "string", "description": "Email address" },
    "middle_name": { "type": "string", "description": "Middle name" }
  },
  "required": ["name", "email", "middle_name"],
  "additionalProperties": false
}
```

### How the LLM Handles Missing Data

Since all fields must be required in strict mode, the LLM handles missing data as follows:

- **String fields**: Returns empty string `""` if data not found in document
- **Number/Integer fields**: Returns `0` if data not found
- **Boolean fields**: Returns `false` if data not found
- **Array fields**: Returns empty array `[]` if data not found
- **Object fields**: Returns object with all nested required fields populated with default values

**Best Practice:** Design your schema knowing that all fields will always be present in the response, but may contain empty/default values when data is not found in the document.

---

## Advanced Schema Features

**⚠️ PORTABILITY WARNING:** The features below are supported by OpenAI's Structured Outputs, but **not recommended** for DocRouter schemas. These constraints may not be portable across different LLM providers (Anthropic Claude, Google Gemini, etc.). For maximum compatibility and reliability:

- **Use basic types only**: string, number, integer, boolean, array, object
- **Avoid** enums, patterns, minimum/maximum, minItems/maxItems, uniqueItems
- **Handle validation in your application code** instead of in the schema
- **Use detailed descriptions** to guide the LLM rather than strict constraints

### Enums (Restricted Values) - ⚠️ NOT RECOMMENDED

While OpenAI supports limiting field values to specific options, this feature may not work with other LLM providers:

```json
{
  "document_type": {
    "type": "string",
    "description": "Type of document",
    "enum": ["invoice", "receipt", "contract", "bill"]
  }
}
```

**Better approach:**
```json
{
  "document_type": {
    "type": "string",
    "description": "Type of document (e.g., invoice, receipt, contract, or bill)"
  }
}
```

### String Patterns - ⚠️ NOT RECOMMENDED

Regex validation is OpenAI-specific and reduces portability:

```json
{
  "phone": {
    "type": "string",
    "description": "Phone number in E.164 format",
    "pattern": "^\\+[1-9]\\d{1,14}$"
  }
}
```

**Better approach:**
```json
{
  "phone": {
    "type": "string",
    "description": "Phone number in E.164 format (e.g., +1234567890)"
  }
}
```

### Number Constraints - ⚠️ NOT RECOMMENDED

Minimum, maximum, and multipleOf constraints may not be portable:

```json
{
  "age": {
    "type": "integer",
    "description": "Age in years",
    "minimum": 0,
    "maximum": 150
  },
  "price": {
    "type": "number",
    "description": "Price in USD",
    "minimum": 0,
    "multipleOf": 0.01
  }
}
```

**Better approach:**
```json
{
  "age": {
    "type": "integer",
    "description": "Age in years (0-150)"
  },
  "price": {
    "type": "number",
    "description": "Price in USD (e.g., 19.99)"
  }
}
```

### Array Constraints - ⚠️ NOT RECOMMENDED

Array size and uniqueness constraints are not universally supported:

```json
{
  "tags": {
    "type": "array",
    "description": "Document tags",
    "items": {
      "type": "string"
    },
    "minItems": 1,
    "maxItems": 10,
    "uniqueItems": true
  }
}
```

**Better approach:**
```json
{
  "tags": {
    "type": "array",
    "description": "Document tags (1-10 unique tags)",
    "items": {
      "type": "string"
    }
  }
}
```

### Complex Nested Objects

```json
{
  "work_history": {
    "type": "array",
    "description": "Employment history",
    "items": {
      "type": "object",
      "properties": {
        "company": {
          "type": "string",
          "description": "Company name"
        },
        "position": {
          "type": "string",
          "description": "Job title"
        },
        "start_date": {
          "type": "string",
          "description": "Start date (YYYY-MM-DD)"
        },
        "end_date": {
          "type": "string",
          "description": "End date (YYYY-MM-DD or 'Present')"
        },
        "responsibilities": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "List of job responsibilities"
        }
      },
      "required": ["company", "position", "start_date", "end_date", "responsibilities"],
      "additionalProperties": false
    }
  }
}
```

---

## Best Practices

### 1. Use Clear, Descriptive Field Names

**Good:**
```json
"current_academic_program": { "type": "string", "description": "Current degree program" }
```

**Avoid:**
```json
"prog": { "type": "string", "description": "program" }
```

### 2. Provide Detailed Descriptions

Descriptions guide the LLM on what to extract:

**Good:**
```json
{
  "total_amount": {
    "type": "string",
    "description": "Total invoice amount including tax, with currency symbol and commas (e.g., $1,234.56)"
  }
}
```

**Avoid:**
```json
{
  "total_amount": {
    "type": "string",
    "description": "total"
  }
}
```

### 3. Choose Appropriate Field Types

- Use **string** for currency values with formatting (e.g., "$1,234.56")
- Use **number** for numeric calculations
- Use **array** for multiple items instead of comma-separated strings
- Use **object** to group related fields

### 4. Set `additionalProperties: false`

Prevent the LLM from adding unexpected fields:

```json
{
  "type": "object",
  "properties": { ... },
  "additionalProperties": false
}
```

### 5. All Fields Must Be Required (Strict Mode)

- **ALL fields must be listed in the `required` array** when using `strict: true`
- The LLM will return empty/default values for fields not found in the document
- Design your schema to handle empty values gracefully in your application logic
- There are no optional fields in strict mode - this is an OpenAI API requirement

### 6. Avoid Advanced Constraints for Portability

For maximum portability across LLM providers (OpenAI, Anthropic, Gemini, etc.):

- **Use basic types only** and avoid enums, patterns, min/max constraints
- **Put constraints in descriptions** instead: `"Status (paid, unpaid, overdue, or cancelled)"`
- **Validate data in your application** rather than in the schema
- This ensures your schemas work consistently across all supported LLM providers

**Not recommended:**
```json
{
  "invoice_status": {
    "type": "string",
    "enum": ["paid", "unpaid", "overdue", "cancelled"]
  }
}
```

**Recommended:**
```json
{
  "invoice_status": {
    "type": "string",
    "description": "Invoice status (paid, unpaid, overdue, or cancelled)"
  }
}
```

### 7. Document Your Schema

Include clear descriptions that explain:
- What data to extract
- Expected format
- How to handle edge cases

---

## Examples

### Example 1: Invoice Schema

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "document_extraction",
    "schema": {
      "type": "object",
      "properties": {
        "invoice_number": {
          "type": "string",
          "description": "Unique invoice identifier"
        },
        "invoice_date": {
          "type": "string",
          "description": "Date of invoice in YYYY-MM-DD format"
        },
        "vendor_name": {
          "type": "string",
          "description": "Name of the vendor/supplier"
        },
        "vendor_address": {
          "type": "string",
          "description": "Complete vendor address"
        },
        "customer_name": {
          "type": "string",
          "description": "Name of the customer/buyer"
        },
        "line_items": {
          "type": "array",
          "description": "List of items on the invoice",
          "items": {
            "type": "object",
            "properties": {
              "description": {
                "type": "string",
                "description": "Item description"
              },
              "quantity": {
                "type": "string",
                "description": "Quantity ordered"
              },
              "unit_price": {
                "type": "string",
                "description": "Price per unit with currency"
              },
              "total": {
                "type": "string",
                "description": "Line total with currency"
              }
            },
            "required": ["description", "quantity", "unit_price", "total"],
            "additionalProperties": false
          }
        },
        "subtotal": {
          "type": "string",
          "description": "Subtotal before tax with currency"
        },
        "tax_amount": {
          "type": "string",
          "description": "Tax amount with currency"
        },
        "total_amount": {
          "type": "string",
          "description": "Total amount due with currency"
        },
        "payment_terms": {
          "type": "string",
          "description": "Payment terms (e.g., Net 30, Due on Receipt)"
        }
      },
      "required": [
        "invoice_number",
        "invoice_date",
        "vendor_name",
        "vendor_address",
        "customer_name",
        "line_items",
        "subtotal",
        "tax_amount",
        "total_amount",
        "payment_terms"
      ],
      "additionalProperties": false
    },
    "strict": true
  }
}
```

### Example 2: Resume/CV Schema

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "document_extraction",
    "schema": {
      "type": "object",
      "properties": {
        "Name": {
          "type": "string",
          "description": "Candidate's full name"
        },
        "Email": {
          "type": "string",
          "description": "Email address"
        },
        "Telephone": {
          "type": "string",
          "description": "Phone number"
        },
        "Current Academic Program": {
          "type": "string",
          "description": "Current degree program (e.g., MEng Computing)"
        },
        "Current Grade": {
          "type": "string",
          "description": "Academic year or GPA/grade information"
        },
        "High School Qualification": {
          "type": "string",
          "description": "A-levels, GCSEs, or equivalent qualifications"
        },
        "Programming Languages": {
          "type": "string",
          "description": "Comma-separated list of programming languages"
        },
        "Experiences": {
          "type": "string",
          "description": "Professional or research experiences"
        },
        "Projects": {
          "type": "string",
          "description": "Academic or personal projects with descriptions"
        },
        "Awards": {
          "type": "string",
          "description": "Academic awards, honors, competition placements"
        },
        "Work Experience": {
          "type": "string",
          "description": "Employment history with companies and roles"
        },
        "Extracurricular": {
          "type": "string",
          "description": "Clubs, hobbies, volunteer work, sports"
        },
        "Languages": {
          "type": "string",
          "description": "Spoken languages and proficiency levels"
        }
      },
      "required": [
        "Name",
        "Email",
        "Telephone",
        "Current Academic Program",
        "Current Grade",
        "High School Qualification",
        "Programming Languages",
        "Experiences",
        "Projects",
        "Awards",
        "Work Experience",
        "Extracurricular",
        "Languages"
      ],
      "additionalProperties": false
    },
    "strict": true
  }
}
```

### Example 3: Financial Statement Schema

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "document_extraction",
    "schema": {
      "type": "object",
      "properties": {
        "net_interest_income": {
          "type": "string",
          "description": "Net interest income in thousands with formatting"
        },
        "net_fee_and_commission_income": {
          "type": "string",
          "description": "Net fee and commission income"
        },
        "other_operating_income": {
          "type": "string",
          "description": "Other operating income"
        },
        "credit_loss_expense": {
          "type": "string",
          "description": "Credit loss expense (negative values in parentheses)"
        },
        "net_operating_income": {
          "type": "string",
          "description": "Net operating income"
        },
        "personnel_expenses": {
          "type": "string",
          "description": "Personnel expenses"
        },
        "other_operating_expenses": {
          "type": "string",
          "description": "Other operating expenses"
        },
        "total_expenses": {
          "type": "string",
          "description": "Total expenses"
        },
        "profit_loss_before_tax": {
          "type": "string",
          "description": "Profit/loss before tax"
        },
        "tax_expense_credit": {
          "type": "string",
          "description": "Tax expense or credit"
        },
        "profit_loss_for_the_year": {
          "type": "string",
          "description": "Final profit/loss for the year"
        }
      },
      "required": [
        "net_interest_income",
        "net_fee_and_commission_income",
        "other_operating_income",
        "credit_loss_expense",
        "net_operating_income",
        "personnel_expenses",
        "other_operating_expenses",
        "total_expenses",
        "profit_loss_before_tax",
        "tax_expense_credit",
        "profit_loss_for_the_year"
      ],
      "additionalProperties": false
    },
    "strict": true
  }
}
```

---

## API Integration

DocRouter provides multiple ways to interact with schemas programmatically:

- **TypeScript/JavaScript SDK** - Type-safe client library for Node.js and browsers (see `packages/typescript/docrouter-sdk/`)
- **Python SDK** - Type-safe Python client library (see `packages/python/sdk/`)
- **REST API** - Direct HTTP requests (see API documentation for endpoints)
- **MCP (Model Context Protocol)** - Integration with AI assistants like Claude Code

All methods support the same schema operations: create, list, retrieve, update, delete, and validate against schemas.

---

## Schema Workflow

### 1. Design Phase
- Identify document type and key fields to extract
- Choose appropriate data types for each field
- Design nested structures for complex data
- Remember: ALL fields will be required in strict mode

### 2. Creation Phase
- Create schema using API or UI
- Test with sample documents
- Iterate based on extraction results

### 3. Prompt Integration
- Link schema to extraction prompt
- Configure LLM model (e.g., gpt-4o-mini, gemini-2.0-flash)
- Associate with document tags for automatic processing

### 4. Processing Phase
- Upload documents with appropriate tags
- LLM extracts data according to schema
- Results available via `getLLMResult` API

### 5. Validation Phase
- Review extracted data
- Verify against schema requirements
- Mark as verified when accurate

---

## Troubleshooting

### Common Issues

**Issue:** LLM returns empty strings for all fields
- **Solution:** Check prompt content, ensure it references the schema, verify document has OCR text

**Issue:** Extra fields appear in extraction
- **Solution:** Ensure `additionalProperties: false` is set in schema

**Issue:** Error "all properties must be required when strict is true"
- **Solution:** Ensure ALL properties are listed in the `required` array at every level (including nested objects)

**Issue:** Error "additionalProperties must be false when strict is true"
- **Solution:** Set `additionalProperties: false` on all objects in the schema, including nested objects

**Issue:** Required fields missing from extraction
- **Solution:** This should not happen with `strict: true`. Verify schema matches exactly, check field names

**Issue:** Number fields returned as strings
- **Solution:** For formatted numbers (with commas, currency), use string type. For calculations, use number type.

**Issue:** Array fields contain single concatenated string
- **Solution:** Update prompt to explicitly instruct LLM to return array of items

---

## Version Control

DocRouter maintains schema versioning:

- Each schema update creates a new version
- `schema_version` increments with each change
- `schema_revid` uniquely identifies each version
- Previous versions remain accessible for historical extractions

---

## References

- [JSON Schema Specification](https://json-schema.org/)
- [OpenAI Structured Outputs Documentation](https://platform.openai.com/docs/guides/structured-outputs)
- [DocRouter API Documentation](../README.md)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-11
**Maintained by:** DocRouter Development Team
