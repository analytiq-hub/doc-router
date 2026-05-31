import pytest
from bson import ObjectId
from datetime import datetime, UTC

import analytiq_data as ad
from analytiq_data.llm.bulk_analyze import _needs_execution, bulk_analyze_executions
from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


async def _seed_bulk_analyze_fixtures(test_db):
    tag_id = str(ObjectId())
    prompt_id = str(ObjectId())
    rev_v1_id = ObjectId()
    rev_v2_id = ObjectId()
    doc_missing = ObjectId()
    doc_outdated = ObjectId()
    doc_current = ObjectId()

    await test_db.prompts.insert_one({
        "_id": ObjectId(prompt_id),
        "organization_id": TEST_ORG_ID,
        "name": "Invoice Extract",
    })

    await test_db.prompt_revisions.insert_many([
        {
            "_id": rev_v1_id,
            "prompt_id": prompt_id,
            "prompt_version": 1,
            "organization_id": TEST_ORG_ID,
            "tag_ids": [tag_id],
            "name": "Invoice Extract",
            "content": "v1",
            "model": "gpt-4o-mini",
            "created_at": datetime.now(UTC),
            "created_by": "test",
        },
        {
            "_id": rev_v2_id,
            "prompt_id": prompt_id,
            "prompt_version": 2,
            "organization_id": TEST_ORG_ID,
            "tag_ids": [tag_id],
            "name": "Invoice Extract",
            "content": "v2",
            "model": "gpt-4o-mini",
            "created_at": datetime.now(UTC),
            "created_by": "test",
        },
    ])

    now = datetime.now(UTC)
    await test_db.docs.insert_many([
        {
            "_id": doc_missing,
            "organization_id": TEST_ORG_ID,
            "user_file_name": "missing.pdf",
            "tag_ids": [tag_id],
            "upload_date": now,
            "uploaded_by": "test",
            "state": "llm_completed",
        },
        {
            "_id": doc_outdated,
            "organization_id": TEST_ORG_ID,
            "user_file_name": "outdated.pdf",
            "tag_ids": [tag_id],
            "upload_date": now,
            "uploaded_by": "test",
            "state": "llm_completed",
        },
        {
            "_id": doc_current,
            "organization_id": TEST_ORG_ID,
            "user_file_name": "current.pdf",
            "tag_ids": [tag_id],
            "upload_date": now,
            "uploaded_by": "test",
            "state": "llm_completed",
        },
    ])

    await test_db.llm_runs.insert_many([
        {
            "document_id": str(doc_outdated),
            "prompt_id": prompt_id,
            "prompt_revid": str(rev_v1_id),
            "prompt_version": 1,
            "llm_result": {"field": "old"},
            "updated_llm_result": {"field": "old"},
            "is_edited": False,
            "is_verified": False,
            "created_at": now,
            "updated_at": now,
        },
        {
            "document_id": str(doc_current),
            "prompt_id": prompt_id,
            "prompt_revid": str(rev_v2_id),
            "prompt_version": 2,
            "llm_result": {"field": "new"},
            "updated_llm_result": {"field": "new"},
            "is_edited": False,
            "is_verified": False,
            "created_at": now,
            "updated_at": now,
        },
    ])

    return {
        "tag_id": tag_id,
        "prompt_id": prompt_id,
        "rev_v2_id": str(rev_v2_id),
        "doc_missing": str(doc_missing),
        "doc_outdated": str(doc_outdated),
        "doc_current": str(doc_current),
    }


async def _seed_multi_prompt_fixtures(test_db):
    """Two distinct prompt_ids on the same tag, one document, no existing llm runs."""
    tag_id = str(ObjectId())
    prompt_a_id = str(ObjectId())
    prompt_b_id = str(ObjectId())
    rev_a_id = ObjectId()
    rev_b_id = ObjectId()
    doc_id = ObjectId()
    now = datetime.now(UTC)

    await test_db.prompts.insert_many([
        {"_id": ObjectId(prompt_a_id), "organization_id": TEST_ORG_ID, "name": "Extract Header"},
        {"_id": ObjectId(prompt_b_id), "organization_id": TEST_ORG_ID, "name": "Extract Line Items"},
    ])

    await test_db.prompt_revisions.insert_many([
        {
            "_id": rev_a_id,
            "prompt_id": prompt_a_id,
            "prompt_version": 1,
            "organization_id": TEST_ORG_ID,
            "tag_ids": [tag_id],
            "name": "Extract Header",
            "content": "header",
            "model": "gpt-4o-mini",
            "created_at": now,
            "created_by": "test",
        },
        {
            "_id": rev_b_id,
            "prompt_id": prompt_b_id,
            "prompt_version": 1,
            "organization_id": TEST_ORG_ID,
            "tag_ids": [tag_id],
            "name": "Extract Line Items",
            "content": "lines",
            "model": "gpt-4o-mini",
            "created_at": now,
            "created_by": "test",
        },
    ])

    await test_db.docs.insert_one({
        "_id": doc_id,
        "organization_id": TEST_ORG_ID,
        "user_file_name": "multi-prompt.pdf",
        "tag_ids": [tag_id],
        "upload_date": now,
        "uploaded_by": "test",
        "state": "llm_completed",
    })

    return {
        "tag_id": tag_id,
        "prompt_a_id": prompt_a_id,
        "prompt_b_id": prompt_b_id,
        "rev_a_id": str(rev_a_id),
        "rev_b_id": str(rev_b_id),
        "doc_id": str(doc_id),
    }


@pytest.mark.asyncio
async def test_bulk_analyze_executions_multiple_prompts(test_db, mock_auth, setup_test_models):
    fixtures = await _seed_multi_prompt_fixtures(test_db)
    analytiq_client = ad.common.get_analytiq_client()

    result = await bulk_analyze_executions(
        analytiq_client,
        TEST_ORG_ID,
        fixtures["tag_id"],
        "outdated",
        tag_ids=[fixtures["tag_id"]],
    )

    assert result["total_executions"] == 2
    assert len(result["groups"]) == 2

    groups_by_prompt_id = {g["prompt_id"]: g for g in result["groups"]}
    assert set(groups_by_prompt_id) == {fixtures["prompt_a_id"], fixtures["prompt_b_id"]}

    for prompt_id, rev_id, name in [
        (fixtures["prompt_a_id"], fixtures["rev_a_id"], "Extract Header"),
        (fixtures["prompt_b_id"], fixtures["rev_b_id"], "Extract Line Items"),
    ]:
        group = groups_by_prompt_id[prompt_id]
        assert group["prompt_revid"] == rev_id
        assert group["name"] == name
        assert len(group["executions"]) == 1
        assert group["executions"][0]["document_id"] == fixtures["doc_id"]
        assert group["executions"][0]["document_name"] == "multi-prompt.pdf"

    assert sum(len(g["executions"]) for g in result["groups"]) == result["total_executions"]


@pytest.mark.asyncio
async def test_bulk_analyze_executions_outdated(test_db, mock_auth, setup_test_models):
    fixtures = await _seed_bulk_analyze_fixtures(test_db)
    analytiq_client = ad.common.get_analytiq_client()

    result = await bulk_analyze_executions(
        analytiq_client,
        TEST_ORG_ID,
        fixtures["tag_id"],
        "outdated",
        tag_ids=[fixtures["tag_id"]],
    )

    assert result["total_executions"] == 2
    assert len(result["groups"]) == 1
    group = result["groups"][0]
    assert group["prompt_revid"] == fixtures["rev_v2_id"]
    assert group["prompt_version"] == 2
    exec_doc_ids = {e["document_id"] for e in group["executions"]}
    assert exec_doc_ids == {fixtures["doc_missing"], fixtures["doc_outdated"]}


@pytest.mark.asyncio
async def test_bulk_analyze_executions_missing(test_db, mock_auth, setup_test_models):
    fixtures = await _seed_bulk_analyze_fixtures(test_db)
    analytiq_client = ad.common.get_analytiq_client()

    result = await bulk_analyze_executions(
        analytiq_client,
        TEST_ORG_ID,
        fixtures["tag_id"],
        "missing",
        tag_ids=[fixtures["tag_id"]],
    )

    assert result["total_executions"] == 1
    assert result["groups"][0]["executions"][0]["document_id"] == fixtures["doc_missing"]


@pytest.mark.asyncio
async def test_bulk_analyze_executions_all(test_db, mock_auth, setup_test_models):
    fixtures = await _seed_bulk_analyze_fixtures(test_db)
    analytiq_client = ad.common.get_analytiq_client()

    result = await bulk_analyze_executions(
        analytiq_client,
        TEST_ORG_ID,
        fixtures["tag_id"],
        "all",
        tag_ids=[fixtures["tag_id"]],
    )

    assert result["total_executions"] == 3


@pytest.mark.asyncio
async def test_bulk_analyze_llm_api(test_db, mock_auth, setup_test_models):
    fixtures = await _seed_bulk_analyze_fixtures(test_db)

    response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/llm/bulk-analyze",
        json={
            "tag_id": fixtures["tag_id"],
            "mode": "outdated",
            "document_filters": {
                "tag_ids": [fixtures["tag_id"]],
            },
        },
        headers=get_auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_executions"] == 2
    assert len(data["groups"]) == 1
    assert data["groups"][0]["prompt_version"] == 2


@pytest.mark.parametrize(
    "mode, existing_version, latest_version, expected",
    [
        ("all", None, 2, True),
        ("all", 2, 2, True),
        ("missing", None, 2, True),
        ("missing", 1, 2, False),
        ("outdated", None, 2, True),
        ("outdated", 1, 2, True),
        ("outdated", 2, 2, False),
    ],
)
def test_needs_execution(mode, existing_version, latest_version, expected):
    assert _needs_execution(mode, latest_version, existing_version) is expected


@pytest.mark.asyncio
async def test_bulk_analyze_executions_no_prompts_for_tag(test_db, mock_auth, setup_test_models):
    analytiq_client = ad.common.get_analytiq_client()
    empty_tag_id = str(ObjectId())

    result = await bulk_analyze_executions(
        analytiq_client,
        TEST_ORG_ID,
        empty_tag_id,
        "outdated",
    )

    assert result == {"total_executions": 0, "groups": []}


@pytest.mark.asyncio
async def test_bulk_analyze_executions_no_matching_documents(test_db, mock_auth, setup_test_models):
    fixtures = await _seed_bulk_analyze_fixtures(test_db)
    analytiq_client = ad.common.get_analytiq_client()

    result = await bulk_analyze_executions(
        analytiq_client,
        TEST_ORG_ID,
        fixtures["tag_id"],
        "outdated",
        tag_ids=[fixtures["tag_id"]],
        name_search="definitely-not-a-real-document-name-xyz",
    )

    assert result == {"total_executions": 0, "groups": []}


def _post_bulk_analyze(tag_id: str, mode: str, tag_ids: list[str] | None = None):
    document_filters: dict = {"tag_ids": tag_ids or [tag_id]}
    return client.post(
        f"/v0/orgs/{TEST_ORG_ID}/llm/bulk-analyze",
        json={
            "tag_id": tag_id,
            "mode": mode,
            "document_filters": document_filters,
        },
        headers=get_auth_headers(),
    )


@pytest.mark.asyncio
async def test_bulk_analyze_llm_api_missing_mode(test_db, mock_auth, setup_test_models):
    fixtures = await _seed_bulk_analyze_fixtures(test_db)

    response = _post_bulk_analyze(fixtures["tag_id"], "missing")

    assert response.status_code == 200
    data = response.json()
    assert data["total_executions"] == 1
    assert data["groups"][0]["executions"][0]["document_id"] == fixtures["doc_missing"]


@pytest.mark.asyncio
async def test_bulk_analyze_llm_api_all_mode(test_db, mock_auth, setup_test_models):
    fixtures = await _seed_bulk_analyze_fixtures(test_db)

    response = _post_bulk_analyze(fixtures["tag_id"], "all")

    assert response.status_code == 200
    data = response.json()
    assert data["total_executions"] == 3
    assert len(data["groups"]) == 1
    exec_doc_ids = {e["document_id"] for e in data["groups"][0]["executions"]}
    assert exec_doc_ids == {
        fixtures["doc_missing"],
        fixtures["doc_outdated"],
        fixtures["doc_current"],
    }
