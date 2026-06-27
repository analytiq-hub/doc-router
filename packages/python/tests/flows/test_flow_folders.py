"""Flow folder tree HTTP CRUD tests."""

from __future__ import annotations

import pytest

from tests.conftest_utils import TEST_ORG_ID, client, get_auth_headers


@pytest.mark.asyncio
async def test_create_and_list_folders(test_db, mock_auth) -> None:
    r = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders",
        json={"name": "Agents", "parent_folder_id": None, "sort_order": 0},
        headers=get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    folder_id = r.json()["folder_id"]

    r_list = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders",
        headers=get_auth_headers(),
    )
    assert r_list.status_code == 200, r_list.text
    items = r_list.json()["items"]
    assert len(items) == 1
    assert items[0]["folder_id"] == folder_id
    assert items[0]["name"] == "Agents"
    assert items[0]["flow_count"] == 0


@pytest.mark.asyncio
async def test_nested_folders_and_delete_empty(test_db, mock_auth) -> None:
    r_parent = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders",
        json={"name": "Parent", "parent_folder_id": None, "sort_order": 0},
        headers=get_auth_headers(),
    )
    parent_id = r_parent.json()["folder_id"]

    r_child = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders",
        json={"name": "Child", "parent_folder_id": parent_id, "sort_order": 0},
        headers=get_auth_headers(),
    )
    assert r_child.status_code == 200, r_child.text
    child_id = r_child.json()["folder_id"]

    r_list = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders",
        headers=get_auth_headers(),
    )
    tree = r_list.json()["items"]
    assert len(tree) == 1
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["folder_id"] == child_id

    r_del_child = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders/{child_id}",
        headers=get_auth_headers(),
    )
    assert r_del_child.status_code == 200, r_del_child.text

    r_del_parent = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders/{parent_id}",
        headers=get_auth_headers(),
    )
    assert r_del_parent.status_code == 200, r_del_parent.text


@pytest.mark.asyncio
async def test_delete_nonempty_folder_rejected(test_db, mock_auth) -> None:
    r_folder = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders",
        json={"name": "HasChild", "parent_folder_id": None, "sort_order": 0},
        headers=get_auth_headers(),
    )
    parent_id = r_folder.json()["folder_id"]

    r_child = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders",
        json={"name": "Nested", "parent_folder_id": parent_id, "sort_order": 0},
        headers=get_auth_headers(),
    )
    child_id = r_child.json()["folder_id"]

    r_del = client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders/{parent_id}",
        headers=get_auth_headers(),
    )
    assert r_del.status_code == 409, r_del.text
    assert "not empty" in r_del.json()["detail"].lower()

    client.delete(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders/{child_id}",
        headers=get_auth_headers(),
    )


@pytest.mark.asyncio
async def test_patch_flow_folder_id(test_db, mock_auth) -> None:
    r_folder = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders",
        json={"name": "Target", "parent_folder_id": None, "sort_order": 0},
        headers=get_auth_headers(),
    )
    folder_id = r_folder.json()["folder_id"]

    r_flow = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows",
        json={"name": "Foldered flow"},
        headers=get_auth_headers(),
    )
    flow_id = r_flow.json()["flow"]["flow_id"]

    r_patch = client.patch(
        f"/v0/orgs/{TEST_ORG_ID}/flows/{flow_id}",
        json={"folder_id": folder_id},
        headers=get_auth_headers(),
    )
    assert r_patch.status_code == 200, r_patch.text

    r_list = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders",
        headers=get_auth_headers(),
    )
    assert r_list.json()["items"][0]["flow_count"] == 1


@pytest.mark.asyncio
async def test_duplicate_sibling_folder_name_rejected(test_db, mock_auth) -> None:
    payload = {"name": "Dup", "parent_folder_id": None, "sort_order": 0}
    r1 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders",
        json=payload,
        headers=get_auth_headers(),
    )
    assert r1.status_code == 200, r1.text

    r2 = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/flows/folders",
        json=payload,
        headers=get_auth_headers(),
    )
    assert r2.status_code == 400, r2.text
    assert "unique" in r2.json()["detail"].lower()
