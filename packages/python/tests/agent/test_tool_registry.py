"""Tests for agent tool registry: definitions and execute_tool dispatch."""
import json
import pytest

# Import from packages/python context
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analytiq_data.agent.tool_registry import (
    TOOL_DEFINITIONS,
    execute_tool,
    READ_ONLY_TOOLS,
    READ_WRITE_TOOLS,
    is_read_only_tool,
)


def test_read_only_and_read_write_tools():
    """Read-only and read-write sets are disjoint and cover all defined tools."""
    all_names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert READ_ONLY_TOOLS | READ_WRITE_TOOLS == all_names
    assert READ_ONLY_TOOLS & READ_WRITE_TOOLS == set()
    assert is_read_only_tool("help_schemas")
    assert not is_read_only_tool("create_schema")


def test_tool_definitions_count():
    """Assert reasonable count and presence of key tools. Avoid exact count to reduce brittleness."""
    assert len(TOOL_DEFINITIONS) >= 20
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert "create_schema" in names
    assert "get_ocr_text" in names
    assert "help_schemas" in names
    assert "run_extraction" in names


def test_tool_definitions_have_required_fields():
    for t in TOOL_DEFINITIONS:
        assert t["type"] == "function"
        fn = t["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"


@pytest.mark.asyncio
async def test_help_schemas_returns_content():
    context = {}
    result_str = await execute_tool("help_schemas", context, "{}")
    result = json.loads(result_str)
    assert "content" in result
    assert "json_schema" in result["content"] or "Schema" in result["content"]


@pytest.mark.asyncio
async def test_help_prompts_returns_content():
    context = {}
    result_str = await execute_tool("help_prompts", context, "{}")
    result = json.loads(result_str)
    assert "content" in result


@pytest.mark.asyncio
async def test_unknown_tool_returns_error():
    result_str = await execute_tool("nonexistent_tool", {}, "{}")
    result = json.loads(result_str)
    assert "error" in result
    assert "Unknown tool" in result["error"]


@pytest.mark.asyncio
async def test_validate_schema_valid():
    context = {}
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "test",
            "schema": {
                "type": "object",
                "properties": {"x": {"type": "string", "description": "X"}},
                "required": ["x"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }
    result_str = await execute_tool("validate_schema", context, json.dumps({"schema": schema}))
    result = json.loads(result_str)
    assert result.get("valid") is True


@pytest.mark.asyncio
async def test_validate_schema_invalid():
    context = {}
    # Missing required "schema" in json_schema, or invalid structure
    result_str = await execute_tool(
        "validate_schema",
        context,
        json.dumps({"schema": {"type": "json_schema", "json_schema": {"name": "x"}}}),
    )
    result = json.loads(result_str)
    assert result.get("valid") is False or "error" in result
