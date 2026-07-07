import pytest
from tests.conftest_utils import client, get_token_headers

import logging
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_schema_permissions(org_and_users, test_db):
    org_id = org_and_users["org_id"]
    admin = org_and_users["admin"]
    member = org_and_users["member"]
    outsider = org_and_users["outsider"]

    # Test schema creation permissions
    schema_data = {
        "name": "Test Schema",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "test_schema",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field1": {
                            "type": "string",
                            "description": "Test field 1"
                        }
                    },
                    "required": ["field1"]
                },
                "strict": True
            }
        }
    }

    # Admin can create schema
    resp = client.post(f"/v0/orgs/{org_id}/schemas", json=schema_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Admin should be able to create schema, got {resp.status_code}: {resp.text}"
    schema_revid = resp.json()["schema_revid"]
    schema_id = resp.json()["schema_id"]

    # Member can create schema
    member_schema_data = {
        "name": "Member Schema",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "member_schema",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field2": {
                            "type": "string",
                            "description": "Test field 2"
                        }
                    },
                    "required": ["field2"]
                },
                "strict": True
            }
        }
    }
    resp = client.post(f"/v0/orgs/{org_id}/schemas", json=member_schema_data, headers=get_token_headers(member["token"]))
    assert resp.status_code == 200, f"Member should be able to create schema, got {resp.status_code}: {resp.text}"
    member_schema_revid = resp.json()["schema_revid"]
    member_schema_id = resp.json()["schema_id"]

    # Outsider cannot create schema
    outsider_schema_data = {
        "name": "Outsider Schema",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "outsider_schema",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field3": {
                            "type": "string",
                            "description": "Test field 3"
                        }
                    },
                    "required": ["field3"]
                },
                "strict": True
            }
        }
    }
    resp = client.post(f"/v0/orgs/{org_id}/schemas", json=outsider_schema_data, headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to create schema, got {resp.status_code}: {resp.text}"

    # Test schema listing permissions
    # Admin can list schemas
    resp = client.get(f"/v0/orgs/{org_id}/schemas", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Admin should be able to list schemas, got {resp.status_code}: {resp.text}"

    # Member can list schemas
    resp = client.get(f"/v0/orgs/{org_id}/schemas", headers=get_token_headers(member["token"]))
    assert resp.status_code == 200, f"Member should be able to list schemas, got {resp.status_code}: {resp.text}"

    # Outsider cannot list schemas
    resp = client.get(f"/v0/orgs/{org_id}/schemas", headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to list schemas, got {resp.status_code}: {resp.text}"

    # Test schema retrieval permissions
    # Admin can get schema
    resp = client.get(f"/v0/orgs/{org_id}/schemas/{schema_revid}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Admin should be able to get schema, got {resp.status_code}: {resp.text}"

    # Member can get schema
    resp = client.get(f"/v0/orgs/{org_id}/schemas/{schema_revid}", headers=get_token_headers(member["token"]))
    assert resp.status_code == 200, f"Member should be able to get schema, got {resp.status_code}: {resp.text}"

    # Outsider cannot get schema
    resp = client.get(f"/v0/orgs/{org_id}/schemas/{schema_revid}", headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to get schema, got {resp.status_code}: {resp.text}"

    # Test schema update permissions
    update_schema_data = {
        "name": "Updated Test Schema",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "update_schema",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field1": {
                            "type": "string",
                            "description": "Updated field 1"
                        },
                        "field2": {
                            "type": "number",
                            "description": "Updated field 2"
                        }
                    },
                    "required": ["field1", "field2"]
                },
                "strict": True
            }
        }
    }

    # Admin can update schema
    resp = client.put(f"/v0/orgs/{org_id}/schemas/{schema_id}", json=update_schema_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Admin should be able to update schema, got {resp.status_code}: {resp.text}"

    # Member can update schema
    member_update_data = {
        "name": "Updated Member Schema",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "member_update_schema",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field2": {
                            "type": "string",
                            "description": "Updated member field 2"
                        },
                        "field3": {
                            "type": "boolean",
                            "description": "Updated member field 3"
                        }
                    },
                    "required": ["field2", "field3"]
                },
                "strict": True
            }
        }
    }
    resp = client.put(f"/v0/orgs/{org_id}/schemas/{member_schema_id}", json=member_update_data, headers=get_token_headers(member["token"]))
    assert resp.status_code == 200, f"Member should be able to update schema, got {resp.status_code}: {resp.text}"

    # Outsider cannot update schema
    outsider_update_data = {
        "name": "Outsider Update Attempt",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "outsider_update_schema",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field4": {
                            "type": "string",
                            "description": "Outsider field 4"
                        }
                    },
                    "required": ["field4"]
                },
                "strict": True
            }
        }
    }
    resp = client.put(f"/v0/orgs/{org_id}/schemas/{schema_revid}", json=outsider_update_data, headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to update schema, got {resp.status_code}: {resp.text}"

    # Test schema validation permissions
    validation_data = {
        "data": {
            "field1": "test value",
            "field2": 42
        }
    }

    # Admin can validate against schema
    resp = client.post(f"/v0/orgs/{org_id}/schemas/{schema_revid}/validate", json=validation_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code in (200, 400)  # 200 if valid, 400 if invalid

    # Member can validate against schema
    resp = client.post(f"/v0/orgs/{org_id}/schemas/{schema_revid}/validate", json=validation_data, headers=get_token_headers(member["token"]))
    assert resp.status_code in (200, 400)

    # Outsider cannot validate against schema
    resp = client.post(f"/v0/orgs/{org_id}/schemas/{schema_revid}/validate", json=validation_data, headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403), f"Outsider should NOT be able to validate against schema, got {resp.status_code}: {resp.text}"

    # Test schema deletion permissions
    # Create a schema for deletion testing
    delete_test_schema_data = {
        "name": "Delete Test Schema",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "delete_test_schema",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field5": {
                            "type": "string",
                            "description": "Delete test field 5"
                        }
                    },
                    "required": ["field5"]
                },
                "strict": True
            }
        }
    }
    resp = client.post(f"/v0/orgs/{org_id}/schemas", json=delete_test_schema_data, headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Admin should be able to create schema, got {resp.status_code}: {resp.text}"
    delete_schema_revid = resp.json()["schema_revid"]
    delete_schema_id = resp.json()["schema_id"]

    # Admin can delete schema
    resp = client.delete(f"/v0/orgs/{org_id}/schemas/{delete_schema_id}", headers=get_token_headers(admin["token"]))
    assert resp.status_code == 200, f"Admin should be able to delete schema, got {resp.status_code}: {resp.text}"

    # Create another schema for member deletion test
    member_delete_schema_data = {
        "name": "Member Delete Test Schema",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "member_delete_schema",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field6": {
                            "type": "string",
                            "description": "Member delete test field 6"
                        }
                    },
                    "required": ["field6"]
                },
                "strict": True
            }
        }
    }
    resp = client.post(f"/v0/orgs/{org_id}/schemas", json=member_delete_schema_data, headers=get_token_headers(member["token"]))
    assert resp.status_code == 200, f"Member should be able to create schema, got {resp.status_code}: {resp.text}"
    member_delete_schema_revid = resp.json()["schema_revid"]
    member_delete_schema_id = resp.json()["schema_id"]

    # Member can delete schema
    resp = client.delete(f"/v0/orgs/{org_id}/schemas/{member_delete_schema_id}", headers=get_token_headers(member["token"]))
    assert resp.status_code == 200, f"Member should be able to delete schema, got {resp.status_code}: {resp.text}"

    # Outsider cannot delete schema
    resp = client.delete(f"/v0/orgs/{org_id}/schemas/{schema_revid}", headers=get_token_headers(outsider["token"]))
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_update_schema_cross_tenant_denied(org_and_users, test_db):
    """A member of org B cannot update a schema that belongs to org A."""
    from bson import ObjectId
    from datetime import datetime, UTC
    import secrets
    import analytiq_data as ad
    from app.routes.payments import sync_payments_customer

    org_a_id = org_and_users["org_id"]
    member = org_and_users["member"]

    schema_data = {
        "name": "Org A Schema",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "org_a_schema",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"field1": {"type": "string"}},
                    "required": ["field1"],
                },
                "strict": True,
            },
        },
    }
    resp = client.post(
        f"/v0/orgs/{org_a_id}/schemas",
        json=schema_data,
        headers=get_token_headers(member["token"]),
    )
    assert resp.status_code == 200
    schema_id = resp.json()["schema_id"]
    original_name = resp.json()["name"]

    org_b_id = str(ObjectId())
    await test_db.organizations.insert_one({
        "_id": ObjectId(org_b_id),
        "name": "Other Org",
        "members": [{"user_id": member["id"], "role": "user"}],
        "type": "team",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    })
    await sync_payments_customer(test_db, org_b_id)

    org_b_token = f"org_{secrets.token_urlsafe(32)}"
    await test_db.access_tokens.insert_one({
        "user_id": member["id"],
        "organization_id": org_b_id,
        "name": "member-org-b-token",
        "token": ad.crypto.encrypt_secret(org_b_token),
        "fingerprint": ad.crypto.fingerprint_secret(org_b_token),
        "created_at": datetime.now(UTC),
        "lifetime": 30,
    })

    resp = client.put(
        f"/v0/orgs/{org_b_id}/schemas/{schema_id}",
        json={"name": "Cross-tenant overwrite attempt"},
        headers=get_token_headers(org_b_token),
    )
    assert resp.status_code == 404, f"Expected 404 for cross-tenant update, got {resp.status_code}: {resp.text}"

    schema_doc = await test_db.schemas.find_one({"_id": ObjectId(schema_id)})
    assert schema_doc["name"] == original_name
    assert schema_doc["organization_id"] == org_a_id 