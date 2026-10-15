"""Map document agent tools to org capabilities (phase 4)."""

from __future__ import annotations

from typing import Any, Iterable

from analytiq_data.org_permissions import (
    ALL_CAPABILITIES,
    CAPABILITY_CONFIG_READ,
    CAPABILITY_CONFIG_WRITE,
    CAPABILITY_DOCUMENTS_READ,
    CAPABILITY_DOCUMENTS_WRITE,
    CAPABILITY_RUNS_EXECUTE,
    load_org_member_context,
)

# Required capability per tool name (must cover every registered agent tool).
TOOL_REQUIRED_CAPABILITY: dict[str, str] = {
    "get_ocr_text": CAPABILITY_DOCUMENTS_READ,
    "get_extraction_result": CAPABILITY_DOCUMENTS_READ,
    "list_documents": CAPABILITY_DOCUMENTS_READ,
    "list_cases": CAPABILITY_DOCUMENTS_READ,
    "get_case": CAPABILITY_DOCUMENTS_READ,
    "update_document": CAPABILITY_DOCUMENTS_WRITE,
    "delete_document": CAPABILITY_DOCUMENTS_WRITE,
    "update_extraction_field": CAPABILITY_DOCUMENTS_WRITE,
    "create_case": CAPABILITY_DOCUMENTS_WRITE,
    "update_case": CAPABILITY_DOCUMENTS_WRITE,
    "delete_case": CAPABILITY_DOCUMENTS_WRITE,
    "assign_documents_to_case": CAPABILITY_DOCUMENTS_WRITE,
    "run_extraction": CAPABILITY_RUNS_EXECUTE,
    "get_schema": CAPABILITY_CONFIG_READ,
    "list_schemas": CAPABILITY_CONFIG_READ,
    "validate_schema": CAPABILITY_CONFIG_READ,
    "validate_against_schema": CAPABILITY_CONFIG_READ,
    "get_prompt": CAPABILITY_CONFIG_READ,
    "list_prompts": CAPABILITY_CONFIG_READ,
    "get_tag": CAPABILITY_CONFIG_READ,
    "list_tags": CAPABILITY_CONFIG_READ,
    "help_schemas": CAPABILITY_CONFIG_READ,
    "help_prompts": CAPABILITY_CONFIG_READ,
    "list_llm_models": CAPABILITY_CONFIG_READ,
    "create_schema": CAPABILITY_CONFIG_WRITE,
    "update_schema": CAPABILITY_CONFIG_WRITE,
    "delete_schema": CAPABILITY_CONFIG_WRITE,
    "create_prompt": CAPABILITY_CONFIG_WRITE,
    "update_prompt": CAPABILITY_CONFIG_WRITE,
    "delete_prompt": CAPABILITY_CONFIG_WRITE,
    "create_tag": CAPABILITY_CONFIG_WRITE,
    "update_tag": CAPABILITY_CONFIG_WRITE,
    "delete_tag": CAPABILITY_CONFIG_WRITE,
}


def required_capability_for_tool(tool_name: str) -> str | None:
    return TOOL_REQUIRED_CAPABILITY.get(tool_name)


def member_has_tool_capability(capabilities: Iterable[str], tool_name: str) -> bool:
    required = required_capability_for_tool(tool_name)
    if required is None:
        return False
    return required in capabilities


def tool_definitions_for_capabilities(capabilities: Iterable[str]) -> list[dict[str, Any]]:
    from .tool_registry import TOOL_DEFINITIONS

    allowed = allowed_tool_names(capabilities)
    return [
        t
        for t in TOOL_DEFINITIONS
        if (t.get("function") or {}).get("name") in allowed
    ]


def allowed_tool_names(capabilities: Iterable[str]) -> frozenset[str]:
    caps = set(capabilities)
    return frozenset(
        name
        for name in TOOL_REQUIRED_CAPABILITY
        if TOOL_REQUIRED_CAPABILITY[name] in caps
    )


def filter_tools_metadata(
    capabilities: Iterable[str],
) -> tuple[list[str], list[str]]:
    from .tool_registry import READ_ONLY_TOOLS, READ_WRITE_TOOLS

    allowed = allowed_tool_names(capabilities)
    read_only = sorted(n for n in READ_ONLY_TOOLS if n in allowed)
    read_write = sorted(n for n in READ_WRITE_TOOLS if n in allowed)
    return read_only, read_write


async def load_member_capabilities(analytiq_client, organization_id: str, user_id: str) -> frozenset[str]:
    import analytiq_data as ad

    db = ad.common.get_async_db(analytiq_client)
    ctx = await load_org_member_context(db, organization_id, user_id)
    if ctx is None:
        return frozenset()
    return ctx.capabilities


async def ensure_context_capabilities(context: dict) -> frozenset[str]:
    caps = context.get("capabilities")
    if caps is not None:
        if isinstance(caps, frozenset):
            return caps
        return frozenset(caps)

    org_id = context.get("organization_id")
    user_id = context.get("created_by")
    client = context.get("analytiq_client")
    if not org_id or not user_id or not client:
        return frozenset()

    loaded = await load_member_capabilities(client, org_id, user_id)
    context["capabilities"] = loaded
    return loaded


def assert_tools_registry_complete(tool_handler_names: Iterable[str]) -> None:
    """Raise if any handler lacks a capability mapping."""
    missing = set(tool_handler_names) - set(TOOL_REQUIRED_CAPABILITY)
    if missing:
        raise ValueError(f"Agent tools missing capability mapping: {sorted(missing)}")
    unknown_caps = set(TOOL_REQUIRED_CAPABILITY.values()) - set(ALL_CAPABILITIES)
    if unknown_caps:
        raise ValueError(f"Agent tool capabilities not in catalog: {sorted(unknown_caps)}")
