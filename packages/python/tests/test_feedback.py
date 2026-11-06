"""Feedback API (FastAPI) — migrated from Next route handlers."""

from datetime import UTC, datetime

import bcrypt
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

import analytiq_data as ad
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


@pytest.mark.asyncio
async def test_submit_feedback_authenticated(client, worker_db_name):
    db = ad.common.get_async_db()
    result = await db.users.insert_one({
        "email": "fb-user@example.com",
        "password": _hash_password("pw"),
        "name": "FB User",
        "email_verified": True,
        "created_at": datetime.now(UTC),
    })
    user_id = str(result.inserted_id)

    login = client.post(
        "/v0/account/auth/login",
        json={"email": "fb-user@example.com", "password": "pw"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    res = client.post(
        "/v0/feedback",
        json={"feedback": "Great product"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201, res.text
    doc = await db.feedback.find_one({"content": "Great product"})
    assert doc is not None
    assert doc.get("userId") == user_id
    assert doc.get("email") == "fb-user@example.com"


@pytest.mark.asyncio
async def test_admin_feedback_list_and_delete(client, worker_db_name):
    db = ad.common.get_async_db()
    uid = str(
        (
            await db.users.insert_one({
                "email": "admin-fb@example.com",
                "password": _hash_password("pw"),
                "name": "Admin",
                "email_verified": True,
                "system_role": "sysadmin",
                "created_at": datetime.now(UTC),
            })
        ).inserted_id,
    )

    ins = await db.feedback.insert_one({
        "content": "del me",
        "email": "a@b.c",
        "userId": uid,
        "userName": "Admin",
        "createdAt": datetime.now(UTC).isoformat(),
        "status": "new",
    })
    fid = str(ins.inserted_id)

    login = client.post(
        "/v0/account/auth/login",
        json={"email": "admin-fb@example.com", "password": "pw"},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    lst = client.get("/v0/admin/feedback", headers=headers)
    assert lst.status_code == 200
    data = lst.json()
    assert any(x["_id"] == fid for x in data["feedback"])

    deleted = client.delete(f"/v0/admin/feedback/{fid}", headers=headers)
    assert deleted.status_code == 200
    assert await db.feedback.find_one({"_id": ObjectId(fid)}) is None
