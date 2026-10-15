import pytest
from bson import ObjectId

from analytiq_data.agent.tool_capabilities import (
    allowed_tool_names,
    member_has_tool_capability,
    tool_definitions_for_capabilities,
)
from analytiq_data.agent.tool_registry import execute_tool, filter_tools_metadata
from analytiq_data.org_permissions import (
    BUILTIN_OPERATOR,
    BUILTIN_VIEWER,
    CAPABILITY_CONFIG_WRITE,
)


def test_viewer_tool_set_excludes_config_write():
    viewer_caps = frozenset({"documents.read", "config.read"})
    allowed = allowed_tool_names(viewer_caps)
    assert "create_schema" not in allowed
    assert "get_schema" in allowed
    assert "run_extraction" not in allowed


def test_operator_has_runs_and_documents_write_not_config_write():
    operator_caps = frozenset(
        {"documents.read", "config.read", "documents.write", "runs.execute"}
    )
    allowed = allowed_tool_names(operator_caps)
    assert "run_extraction" in allowed
    assert "delete_document" in allowed
    assert "create_prompt" not in allowed
    assert "create_schema" not in allowed


def test_builder_includes_config_write_tools():
    builder_caps = frozenset(
        {
            "documents.read",
            "config.read",
            "documents.write",
            "runs.execute",
            "config.write",
        }
    )
    allowed = allowed_tool_names(builder_caps)
    assert "create_schema" in allowed
    assert "update_prompt" in allowed


def test_tool_definitions_filtered_to_allowed_names():
    caps = frozenset({"documents.read", "config.read"})
    defs = tool_definitions_for_capabilities(caps)
    names = {(d["function"]["name"]) for d in defs}
    assert "list_schemas" in names
    assert "create_schema" not in names


@pytest.mark.asyncio
async def test_execute_tool_denies_config_write_for_operator(org_and_users, test_db):
    import analytiq_data as ad

    org_id = org_and_users["org_id"]
    member_id = org_and_users["member"]["id"]
    await test_db.organizations.update_one(
        {"_id": ObjectId(org_id), "members.user_id": member_id},
        {"$set": {"members.$.permission_group_ids": [BUILTIN_OPERATOR]}},
    )
    ctx = await ad.org_permissions.load_org_member_context(
        test_db, org_id, member_id
    )
    assert ctx is not None
    assert CAPABILITY_CONFIG_WRITE not in ctx.capabilities

    context = {
        "analytiq_client": ad.common.get_analytiq_client(),
        "organization_id": org_id,
        "document_id": "000000000000000000000001",
        "created_by": member_id,
        "capabilities": ctx.capabilities,
    }
    result = await execute_tool(
        "create_schema",
        context,
        {"name": "x", "schema": {"type": "object"}},
    )
    assert "Missing required permission" in result
    assert "config.write" in result


@pytest.mark.asyncio
async def test_chat_tools_endpoint_respects_operator(org_and_users, test_db):
    from tests.conftest_utils import client, get_token_headers

    org_id = org_and_users["org_id"]
    member_id = org_and_users["member"]["id"]
    doc_id = str(ObjectId())
    await test_db.docs.insert_one(
        {
            "_id": ObjectId(doc_id),
            "organization_id": org_id,
            "user_file_name": "t.pdf",
            "upload_date": __import__("datetime").datetime.now(__import__("datetime").UTC),
        }
    )
    await test_db.organizations.update_one(
        {"_id": ObjectId(org_id), "members.user_id": member_id},
        {"$set": {"members.$.permission_group_ids": [BUILTIN_OPERATOR]}},
    )
    resp = client.get(
        f"/v0/orgs/{org_id}/documents/{doc_id}/chat/tools",
        headers=get_token_headers(org_and_users["member"]["token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "create_schema" not in data["read_write"]
    assert "run_extraction" in data["read_write"]


def test_filter_tools_metadata_matches_capability_sets():
    ro, rw = filter_tools_metadata(frozenset({"documents.read", "config.read"}))
    assert "get_tag" in ro
    assert not rw
