"""
OpenAI-compatible tool definitions and dispatch for the document agent.
TOOL_DEFINITIONS is sent to the LLM; execute_tool runs the chosen tool with (context, params).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Callable

from . import tools as agent_tools

logger = logging.getLogger(__name__)

# Read-only tools: never require approval (no create/update/delete).
READ_ONLY_TOOLS: frozenset[str] = frozenset({
    "get_ocr_text",
    "get_extraction_result",
    "list_documents",
    "get_schema",
    "list_schemas",
    "validate_schema",
    "validate_against_schema",
    "get_prompt",
    "list_prompts",
    "get_tag",
    "list_tags",
    "help_schemas",
    "help_prompts",
})

# Read-write tools: require approval unless auto_approve or in auto_approved_tools.
READ_WRITE_TOOLS: frozenset[str] = frozenset({
    "run_extraction",
    "update_extraction_field",
    "update_document",
    "delete_document",
    "create_schema",
    "update_schema",
    "delete_schema",
    "create_prompt",
    "update_prompt",
    "delete_prompt",
    "create_tag",
    "update_tag",
    "delete_tag",
})


def is_read_only_tool(name: str) -> bool:
    return name in READ_ONLY_TOOLS


def is_read_write_tool(name: str) -> bool:
    return name in READ_WRITE_TOOLS


def _json_serial_default(obj: Any) -> Any:
    """Convert non-JSON-serializable values for tool result payloads."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date) and not isinstance(obj, datetime):
        return obj.isoformat()
    try:
        from bson import ObjectId
        if isinstance(obj, ObjectId):
            return str(obj)
    except ImportError:
        pass
    raise TypeError(f"Object of type {type(obj).__name__!r} is not JSON serializable")

# OpenAI function-calling format: list of {"type": "function", "function": {"name", "description", "parameters"}}
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    # Extraction / document
    {
        "type": "function",
        "function": {
            "name": "get_ocr_text",
            "description": "Get OCR text for the current document. Optionally for a specific page (page_num 1-based).",
            "parameters": {
                "type": "object",
                "properties": {"page_num": {"type": "integer", "description": "Optional 1-based page number"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_extraction",
            "description": "Run LLM extraction on the current document with the given prompt. Uses working-state prompt if prompt_revid omitted.",
            "parameters": {
                "type": "object",
                "properties": {"prompt_revid": {"type": "string", "description": "Prompt revision ID (optional)"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_extraction_result",
            "description": "Get the current extraction result for the document for a prompt (or default).",
            "parameters": {
                "type": "object",
                "properties": {"prompt_revid": {"type": "string", "description": "Prompt revision ID (optional)"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_extraction_field",
            "description": "Patch a single field in the current extraction result. path is dot-separated (e.g. invoice_total or line_items.0.amount).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Dot-separated path to the field"},
                    "value": {"description": "New value (any JSON type)"},
                },
                "required": ["path", "value"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "List documents in the organization with optional filters. Same as MCP list_documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skip": {"type": "integer", "description": "Number of documents to skip", "default": 0},
                    "limit": {"type": "integer", "description": "Max documents to return (1-100)", "default": 10},
                    "name_search": {"type": "string", "description": "Search term for document names"},
                    "tag_ids": {"type": "array", "items": {"type": "string"}, "description": "Filter by tag IDs (all must match)"},
                    "metadata_search": {"type": "object", "additionalProperties": {"type": "string"}, "description": "Metadata key-value pairs to filter by"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_document",
            "description": "Update document metadata: name, tag_ids, and/or metadata. Same as MCP update_document. Omit document_id to update the current document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "Document ID (optional; defaults to current document)"},
                    "document_name": {"type": "string", "description": "New display name for the document"},
                    "tag_ids": {"type": "array", "items": {"type": "string"}, "description": "List of tag IDs to set on the document"},
                    "metadata": {"type": "object", "additionalProperties": {"type": "string"}, "description": "Key-value metadata to set (string values only)"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_document",
            "description": "Delete a document and its files. Same as MCP delete_document. Omit document_id to delete the current document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "Document ID (optional; defaults to current document)"},
                },
                "additionalProperties": False,
            },
        },
    },
    # Schema
    {
        "type": "function",
        "function": {
            "name": "create_schema",
            "description": "Create a new schema in the organization. Returns schema_revid.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Schema name"},
                    "response_format": {
                        "type": "object",
                        "description": "Full SchemaResponseFormat: type 'json_schema', json_schema with name, schema (Draft 7), strict true",
                    },
                },
                "required": ["name", "response_format"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_schema",
            "description": "Get full schema definition by schema_revid.",
            "parameters": {
                "type": "object",
                "properties": {"schema_revid": {"type": "string", "description": "Schema revision ID"}},
                "required": ["schema_revid"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_schemas",
            "description": "List schemas in the organization with optional skip, limit, name_search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skip": {"type": "integer", "description": "Number to skip", "default": 0},
                    "limit": {"type": "integer", "description": "Max to return", "default": 10},
                    "name_search": {"type": "string", "description": "Filter by name"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_schema",
            "description": "Create a new version of an existing schema. Returns new schema_revid.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schema_id": {"type": "string", "description": "Stable schema ID"},
                    "name": {"type": "string", "description": "New name (optional)"},
                    "response_format": {"type": "object", "description": "New response format (optional)"},
                },
                "required": ["schema_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_schema",
            "description": "Delete a schema. Fails if prompts depend on it.",
            "parameters": {
                "type": "object",
                "properties": {"schema_id": {"type": "string", "description": "Stable schema ID"}},
                "required": ["schema_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_schema",
            "description": "Validate a schema (JSON string or object) for DocRouter compliance and Draft 7.",
            "parameters": {
                "type": "object",
                "properties": {"schema": {"description": "JSON string or object of the schema"}},
                "required": ["schema"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_against_schema",
            "description": "Validate data against a schema revision.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schema_revid": {"type": "string", "description": "Schema revision ID"},
                    "data": {"description": "Data object to validate"},
                },
                "required": ["schema_revid", "data"],
                "additionalProperties": False,
            },
        },
    },
    # Prompt
    {
        "type": "function",
        "function": {
            "name": "create_prompt",
            "description": "Create a new prompt. Returns prompt_revid.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Prompt name"},
                    "content": {"type": "string", "description": "Prompt text"},
                    "schema_id": {"type": "string", "description": "Optional schema ID to link"},
                    "schema_version": {"type": "integer", "description": "Optional schema version"},
                    "model": {"type": "string", "description": "LLM model", "default": "gpt-4o-mini"},
                    "tag_ids": {"type": "array", "items": {"type": "string"}, "description": "Optional tag IDs"},
                },
                "required": ["name", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_prompt",
            "description": "Get full prompt by prompt_revid.",
            "parameters": {
                "type": "object",
                "properties": {"prompt_revid": {"type": "string", "description": "Prompt revision ID"}},
                "required": ["prompt_revid"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_prompts",
            "description": "List prompts with optional skip, limit, name_search, document_id, tag_ids.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skip": {"type": "integer", "default": 0},
                    "limit": {"type": "integer", "default": 10},
                    "name_search": {"type": "string"},
                    "document_id": {"type": "string"},
                    "tag_ids": {"type": "array", "items": {"type": "string"}},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_prompt",
            "description": "Create a new version of an existing prompt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt_id": {"type": "string", "description": "Stable prompt ID"},
                    "content": {"type": "string"},
                    "schema_id": {"type": "string"},
                    "tag_ids": {"type": "array", "items": {"type": "string"}},
                    "model": {"type": "string"},
                },
                "required": ["prompt_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_prompt",
            "description": "Delete a prompt.",
            "parameters": {
                "type": "object",
                "properties": {"prompt_id": {"type": "string"}},
                "required": ["prompt_id"],
                "additionalProperties": False,
            },
        },
    },
    # Tag
    {
        "type": "function",
        "function": {
            "name": "create_tag",
            "description": "Create a new tag. Returns tag_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "color": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tag",
            "description": "Get tag by tag_id.",
            "parameters": {
                "type": "object",
                "properties": {"tag_id": {"type": "string"}},
                "required": ["tag_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tags",
            "description": "List tags with optional skip, limit, name_search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skip": {"type": "integer", "default": 0},
                    "limit": {"type": "integer", "default": 10},
                    "name_search": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_tag",
            "description": "Update a tag's name, color, or description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tag_id": {"type": "string"},
                    "name": {"type": "string"},
                    "color": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["tag_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_tag",
            "description": "Delete a tag. Fails if used by documents or prompts.",
            "parameters": {
                "type": "object",
                "properties": {"tag_id": {"type": "string"}},
                "required": ["tag_id"],
                "additionalProperties": False,
            },
        },
    },
    # Help
    {
        "type": "function",
        "function": {
            "name": "help_schemas",
            "description": "Get detailed guidance on creating schemas (format, constraints, examples). Call before creating or modifying schemas.",
            "parameters": {
                "type": "object",
                "properties": {"_": {"type": "string", "description": "Unused; omit when calling."}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "help_prompts",
            "description": "Get detailed guidance on creating prompts (format, linking to schemas, model selection). Call before creating or modifying prompts.",
            "parameters": {
                "type": "object",
                "properties": {"_": {"type": "string", "description": "Unused; omit when calling."}},
                "additionalProperties": False,
            },
        },
    },
]

# Map tool name -> async fn(context, params)
_TOOL_HANDLERS: dict[str, Callable] = {
    "get_ocr_text": agent_tools.get_ocr_text,
    "run_extraction": agent_tools.run_extraction,
    "get_extraction_result": agent_tools.get_extraction_result,
    "update_extraction_field": agent_tools.update_extraction_field,
    "list_documents": agent_tools.list_documents,
    "update_document": agent_tools.update_document,
    "delete_document": agent_tools.delete_document,
    "create_schema": agent_tools.create_schema,
    "get_schema": agent_tools.get_schema,
    "list_schemas": agent_tools.list_schemas,
    "update_schema": agent_tools.update_schema,
    "delete_schema": agent_tools.delete_schema,
    "validate_schema": agent_tools.validate_schema,
    "validate_against_schema": agent_tools.validate_against_schema,
    "create_prompt": agent_tools.create_prompt,
    "get_prompt": agent_tools.get_prompt,
    "list_prompts": agent_tools.list_prompts,
    "update_prompt": agent_tools.update_prompt,
    "delete_prompt": agent_tools.delete_prompt,
    "create_tag": agent_tools.create_tag,
    "get_tag": agent_tools.get_tag,
    "list_tags": agent_tools.list_tags,
    "update_tag": agent_tools.update_tag,
    "delete_tag": agent_tools.delete_tag,
    "help_schemas": agent_tools.help_schemas,
    "help_prompts": agent_tools.help_prompts,
}


async def execute_tool(name: str, context: dict, arguments: str | dict) -> str:
    """
    Execute a tool by name with the given context and arguments.
    arguments: JSON string (from LLM) or dict. Returns JSON string of the result for the LLM.
    """
    handler = _TOOL_HANDLERS.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})
    if isinstance(arguments, str):
        try:
            params = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON arguments: {e}"})
    else:
        params = arguments or {}
    try:
        result = await handler(context, params)
        return json.dumps(result, default=_json_serial_default)
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return json.dumps({"error": str(e)})
