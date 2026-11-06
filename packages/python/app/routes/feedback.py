"""Product feedback stored in MongoDB (moved from Next.js route handlers)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import analytiq_data as ad
from app.auth import get_admin_user, get_current_user
from app.models import User

logger = logging.getLogger(__name__)

feedback_router = APIRouter(tags=["feedback"])


class FeedbackCreate(BaseModel):
    feedback: str = Field(..., min_length=1)
    userId: str | None = None
    userName: str | None = None
    createdAt: str | None = None


@feedback_router.post("/v0/feedback", status_code=201)
async def submit_feedback(body: FeedbackCreate, user: User = Depends(get_current_user)):
    db = ad.common.get_async_db()
    feedback_doc: dict[str, Any] = {
        "content": body.feedback,
        "email": None,
        "userId": body.userId or user.user_id,
        "userName": body.userName or user.user_name,
        "createdAt": body.createdAt or datetime.now(UTC).isoformat(),
        "status": "new",
    }
    mongo_user = await db.users.find_one({"_id": ObjectId(user.user_id)}, projection={"email": 1})
    if mongo_user and mongo_user.get("email"):
        feedback_doc["email"] = mongo_user["email"]

    await db.feedback.insert_one(feedback_doc)
    return {"success": True, "message": "Feedback submitted successfully"}


@feedback_router.get("/v0/admin/feedback")
async def list_feedback_admin(user: User = Depends(get_admin_user)):
    db = ad.common.get_async_db()
    entries = (
        await db.feedback.find({})
        .sort("createdAt", -1)
        .to_list(length=None)
    )
    for doc in entries:
        doc["_id"] = str(doc["_id"])
    return {"feedback": entries}


@feedback_router.delete("/v0/admin/feedback/{feedback_id}")
async def delete_feedback_admin(feedback_id: str, user: User = Depends(get_admin_user)):
    _ = user
    try:
        oid = ObjectId(feedback_id)
    except InvalidId as e:
        raise HTTPException(status_code=400, detail="Invalid feedback ID") from e
    db = ad.common.get_async_db()
    result = await db.feedback.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"success": True}
