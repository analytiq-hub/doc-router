# DocRouter Forms Configuration Guide

## Overview

Forms in DocRouter provide a human-in-the-loop interface for verifying, editing, and completing AI-extracted data from documents. Forms use the **Form.io JSON format** to define interactive UI components with validation rules and field mappings.

## Table of Contents

1. [What is a Form?](#what-is-a-form)
2. [Form Structure](#form-structure)
3. [Form.io Field Types](#formio-field-types)
4. [Field Validation](#field-validation)
5. [Field Mapping](#field-mapping)
6. [Best Practices](#best-practices)
7. [API Integration](#api-integration)
8. [Examples](#examples)

---

## What is a Form?

A form in DocRouter is an interactive UI definition that:

- Displays AI-extracted data for human review and editing
- Provides validation rules for data quality
- Maps form fields to schema fields from prompt extraction
- Supports workflows for document approval and processing
- Can be tagged to automatically present for specific document types

---

## Form Structure

### Basic Form Format

```json
{
  "name": "Insurance Application Form",
  "response_format": {
    "json_formio": [
      // Array of Form.io field definitions
    ],
    "json_formio_mapping": {
      // Optional field mappings to schema fields
    }
  },
  "tag_ids": ["tag1", "tag2"]
}
```

### Components

| Component | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Human-readable name for the form |
| `response_format` | object | Yes | Contains field definitions and mappings |
| `response_format.json_formio` | array | Yes | Array of Form.io field components |
| `response_format.json_formio_mapping` | object | No | Maps form fields to prompt schema fields |
| `tag_ids` | array | No | Document tags that trigger this form |

---

## Form.io Field Types

DocRouter supports standard Form.io field types for building interactive forms:

### Text Field

```json
{
  "type": "textfield",
  "key": "applicant_name",
  "label": "Applicant Name",
  "input": true,
  "validate": {
    "required": true
  }
}
```

**Use for:** Names, addresses, single-line text input

### Email Field

```json
{
  "type": "email",
  "key": "applicant_email",
  "label": "Email Address",
  "input": true,
  "validate": {
    "required": true
  }
}
```

**Use for:** Email addresses with built-in validation

### Number Field

```json
{
  "type": "number",
  "key": "coverage_amount",
  "label": "Coverage Amount",
  "input": true,
  "validate": {
    "required": true,
    "min": 1000,
    "max": 1000000
  }
}
```

**Use for:** Numeric values, amounts, quantities

### Select/Dropdown Field

```json
{
  "type": "select",
  "key": "policy_type",
  "label": "Policy Type",
  "input": true,
  "data": {
    "values": [
      {"label": "Auto", "value": "auto"},
      {"label": "Home", "value": "home"},
      {"label": "Life", "value": "life"}
    ]
  },
  "validate": {
    "required": true
  }
}
```

**Use for:** Predefined options, categorical data

### Textarea Field

```json
{
  "type": "textarea",
  "key": "notes",
  "label": "Additional Notes",
  "input": true,
  "rows": 5,
  "validate": {
    "required": false
  }
}
```

**Use for:** Multi-line text, comments, descriptions

### Checkbox Field

```json
{
  "type": "checkbox",
  "key": "terms_accepted",
  "label": "I accept the terms and conditions",
  "input": true,
  "validate": {
    "required": true
  }
}
```

**Use for:** Boolean yes/no, agreements, flags

### Date Field

```json
{
  "type": "datetime",
  "key": "application_date",
  "label": "Application Date",
  "input": true,
  "format": "yyyy-MM-dd",
  "validate": {
    "required": true
  }
}
```

**Use for:** Dates, timestamps

### Phone Number Field

```json
{
  "type": "phoneNumber",
  "key": "phone",
  "label": "Phone Number",
  "input": true,
  "validate": {
    "required": true
  }
}
```

**Use for:** Telephone numbers with formatting

---

## Field Validation

Form.io provides built-in validation rules:

### Required Fields

```json
{
  "validate": {
    "required": true
  }
}
```

### Minimum/Maximum Values

```json
{
  "validate": {
    "min": 0,
    "max": 100
  }
}
```

### Minimum/Maximum Length

```json
{
  "validate": {
    "minLength": 5,
    "maxLength": 100
  }
}
```

### Pattern/Regex Validation

```json
{
  "validate": {
    "pattern": "^[A-Z]{2}\\d{6}$"
  }
}
```

### Custom Validation Messages

```json
{
  "validate": {
    "required": true,
    "customMessage": "Please provide a valid policy number"
  }
}
```

---

## Field Mapping

Field mapping connects form fields to AI-extracted data from prompts/schemas:

### Direct Mapping

Maps a single schema field to a form field:

```json
{
  "json_formio_mapping": {
    "applicant_name": {
      "sources": [
        {
          "promptId": "prompt123",
          "promptName": "Insurance Extraction",
          "schemaFieldPath": "applicant.full_name",
          "schemaFieldName": "full_name",
          "schemaFieldType": "string"
        }
      ],
      "mappingType": "direct"
    }
  }
}
```

### Concatenated Mapping

Combines multiple schema fields into one form field:

```json
{
  "json_formio_mapping": {
    "full_name": {
      "sources": [
        {
          "promptId": "prompt123",
          "promptName": "CV Extraction",
          "schemaFieldPath": "personal_info.first_name",
          "schemaFieldName": "first_name",
          "schemaFieldType": "string"
        },
        {
          "promptId": "prompt123",
          "promptName": "CV Extraction",
          "schemaFieldPath": "personal_info.last_name",
          "schemaFieldName": "last_name",
          "schemaFieldType": "string"
        }
      ],
      "mappingType": "concatenated",
      "concatenationSeparator": " "
    }
  }
}
```

### Mapping Components

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `promptId` | string | Yes | ID of the prompt that extracts this data |
| `promptName` | string | Yes | Human-readable prompt name |
| `schemaFieldPath` | string | Yes | Dot-notation path to field in schema |
| `schemaFieldName` | string | Yes | Name of the field in the schema |
| `schemaFieldType` | string | Yes | Data type (string, number, boolean, etc.) |
| `mappingType` | string | Yes | "direct" or "concatenated" |
| `concatenationSeparator` | string | No | Separator for concatenated fields (default: space) |

---

## Best Practices

### 1. Organize Fields Logically

Group related fields together:

```json
[
  {
    "type": "textfield",
    "key": "first_name",
    "label": "First Name"
  },
  {
    "type": "textfield",
    "key": "last_name",
    "label": "Last Name"
  },
  {
    "type": "email",
    "key": "email",
    "label": "Email"
  }
]
```

### 2. Use Clear, Descriptive Labels

**Good:**
```json
{
  "label": "Street Address (Line 1)"
}
```

**Avoid:**
```json
{
  "label": "Addr"
}
```

### 3. Set Appropriate Validation

Match validation rules to data requirements:

```json
{
  "type": "email",
  "validate": {
    "required": true,
    "customMessage": "A valid email address is required for correspondence"
  }
}
```

### 4. Use Field Mapping for Automation

Map form fields to schema fields to auto-populate from AI extraction:

```json
{
  "json_formio_mapping": {
    "email": {
      "sources": [{
        "promptId": "cv_prompt",
        "schemaFieldPath": "personal_info.email"
      }],
      "mappingType": "direct"
    }
  }
}
```

### 5. Choose Appropriate Field Types

- Use `select` for predefined options
- Use `number` for numeric values (enables numeric validation)
- Use `email` for email addresses (enables email validation)
- Use `textarea` for multi-line text

### 6. Provide Helpful Placeholders

```json
{
  "type": "textfield",
  "key": "phone",
  "label": "Phone Number",
  "placeholder": "(555) 123-4567"
}
```

---

## API Integration

DocRouter provides multiple ways to interact with forms programmatically:

- **TypeScript/JavaScript SDK** - Type-safe client library (see `packages/typescript/sdk/`)
- **Python SDK** - Type-safe Python client library (see `packages/python/sdk/`)
- **REST API** - Direct HTTP requests
- **MCP (Model Context Protocol)** - Integration with AI assistants like Claude Code

All methods support: create, list, retrieve, update, delete forms, and submit/retrieve form submissions.

---

## Examples

### Example 1: Simple Contact Form

```json
{
  "name": "Contact Information",
  "response_format": {
    "json_formio": [
      {
        "type": "textfield",
        "key": "full_name",
        "label": "Full Name",
        "input": true,
        "validate": {
          "required": true
        }
      },
      {
        "type": "email",
        "key": "email",
        "label": "Email Address",
        "input": true,
        "validate": {
          "required": true
        }
      },
      {
        "type": "phoneNumber",
        "key": "phone",
        "label": "Phone Number",
        "input": true,
        "validate": {
          "required": false
        }
      }
    ]
  },
  "tag_ids": []
}
```

### Example 2: Insurance Application Form

```json
{
  "name": "Insurance Application",
  "response_format": {
    "json_formio": [
      {
        "type": "textfield",
        "key": "applicant_name",
        "label": "Applicant Name",
        "input": true,
        "validate": {
          "required": true
        }
      },
      {
        "type": "email",
        "key": "applicant_email",
        "label": "Email Address",
        "input": true,
        "validate": {
          "required": true
        }
      },
      {
        "type": "number",
        "key": "coverage_amount",
        "label": "Coverage Amount ($)",
        "input": true,
        "validate": {
          "required": true,
          "min": 1000
        }
      },
      {
        "type": "select",
        "key": "policy_type",
        "label": "Policy Type",
        "input": true,
        "data": {
          "values": [
            {"label": "Auto Insurance", "value": "auto"},
            {"label": "Home Insurance", "value": "home"},
            {"label": "Life Insurance", "value": "life"}
          ]
        },
        "validate": {
          "required": true
        }
      },
      {
        "type": "textarea",
        "key": "additional_notes",
        "label": "Additional Notes",
        "input": true,
        "rows": 4,
        "validate": {
          "required": false
        }
      }
    ]
  },
  "tag_ids": ["insurance"]
}
```

### Example 3: CV Review Form with Mapping

```json
{
  "name": "CV Review Form",
  "response_format": {
    "json_formio": [
      {
        "type": "textfield",
        "key": "candidate_name",
        "label": "Candidate Name",
        "input": true,
        "validate": {
          "required": true
        }
      },
      {
        "type": "email",
        "key": "email",
        "label": "Email",
        "input": true,
        "validate": {
          "required": true
        }
      },
      {
        "type": "phoneNumber",
        "key": "phone",
        "label": "Phone Number",
        "input": true,
        "validate": {
          "required": false
        }
      },
      {
        "type": "textfield",
        "key": "current_position",
        "label": "Current Position",
        "input": true,
        "validate": {
          "required": false
        }
      },
      {
        "type": "textarea",
        "key": "skills",
        "label": "Technical Skills",
        "input": true,
        "rows": 5,
        "validate": {
          "required": false
        }
      }
    ],
    "json_formio_mapping": {
      "candidate_name": {
        "sources": [
          {
            "promptId": "cv_extraction_prompt",
            "promptName": "CV Extraction",
            "schemaFieldPath": "personal_info.name",
            "schemaFieldName": "name",
            "schemaFieldType": "string"
          }
        ],
        "mappingType": "direct"
      },
      "email": {
        "sources": [
          {
            "promptId": "cv_extraction_prompt",
            "promptName": "CV Extraction",
            "schemaFieldPath": "personal_info.email",
            "schemaFieldName": "email",
            "schemaFieldType": "string"
          }
        ],
        "mappingType": "direct"
      },
      "phone": {
        "sources": [
          {
            "promptId": "cv_extraction_prompt",
            "promptName": "CV Extraction",
            "schemaFieldPath": "personal_info.phone",
            "schemaFieldName": "phone",
            "schemaFieldType": "string"
          }
        ],
        "mappingType": "direct"
      }
    }
  },
  "tag_ids": ["cv", "resume"]
}
```

---

## Form Workflow

### 1. Design Phase
- Identify what data needs human review
- Determine required vs optional fields
- Design validation rules
- Plan field mappings to prompt schemas

### 2. Creation Phase
- Create form with Form.io field definitions
- Configure validation rules
- Set up field mappings
- Associate with document tags

### 3. Usage Phase
- Documents uploaded with matching tags trigger form display
- AI-extracted data auto-populates mapped fields
- Human reviewers verify, edit, and submit
- Submitted data is validated and stored

### 4. Submission Management
- Retrieve form submissions via API
- Update submissions if corrections needed
- Mark submissions as verified
- Export data for downstream processing

---

## Troubleshooting

### Common Issues

**Issue:** Form fields not auto-populating from AI extraction
- **Solution:** Verify field mappings reference correct promptId and schemaFieldPath

**Issue:** Validation errors on submission
- **Solution:** Check validate.required and other validation rules match data expectations

**Issue:** Form not displaying for documents
- **Solution:** Ensure document tags match form tag_ids

**Issue:** Field mapping not working
- **Solution:** Verify prompt has run successfully and schema field path is correct

---

## Version Control

DocRouter maintains form versioning:

- Each form update creates a new version (if response_format changes)
- Name-only updates do not create new versions
- `form_version` increments with each structural change
- `form_revid` uniquely identifies each version
- Previous versions remain accessible for historical submissions

---

## References

- [Form.io Documentation](https://help.form.io/)
- [Form.io Field Components](https://help.form.io/userguide/forms/form-components)
- [DocRouter API Documentation](../README.md)
- [Schema Definition Manual](./schemas.md)
- [Prompt Configuration Guide](./prompts.md)

---

**Document Version:** 1.0
**Last Updated:** 2025-01-11
**Maintained by:** DocRouter Development Team
