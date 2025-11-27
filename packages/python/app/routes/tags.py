# tags.py

# Standard library imports
import logging
from datetime import datetime, UTC
from typing import Optional, List
from pydantic import BaseModel

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId

# Local imports
import analytiq_data as ad
from app.auth import get_org_user
from app.models import User

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
tags_router = APIRouter(tags=["tags"])

# Tag models
class TagConfig(BaseModel):
    name: str
    color: str | None = None  # Optional hex color code for UI display
    description: str | None = None

class Tag(TagConfig):
    id: str
    created_at: datetime
    created_by: str

class ListTagsResponse(BaseModel):
    tags: List[Tag]
    total_count: int
    skip: int

# Tag management endpoints
@tags_router.post("/v0/orgs/{organization_id}/tags", response_model=Tag)
async def create_tag(
    organization_id: str,
    tag: TagConfig,
    current_user: User = Depends(get_org_user)
):
    """Create a tag"""
    db = ad.common.get_async_db()
    # Check if tag with this name already exists for this user
    existing_tag = await db.tags.find_one({
        "name": tag.name,
        "organization_id": organization_id
    })
    
    if existing_tag:
        raise HTTPException(
            status_code=400,
            detail=f"Tag with name '{tag.name}' already exists"
        )

    new_tag = {
        "name": tag.name,
        "color": tag.color,
        "description": tag.description,
        "created_at": datetime.now(UTC),
        "created_by": current_user.user_id,
        "organization_id": organization_id  # Add organization_id
    }
    
    result = await db.tags.insert_one(new_tag)
    new_tag["id"] = str(result.inserted_id)
    
    return Tag(**new_tag)

@tags_router.get("/v0/orgs/{organization_id}/tags", response_model=ListTagsResponse)
async def list_tags(
    organization_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    name_search: str = Query(None, description="Search term for tag names"),
    current_user: User = Depends(get_org_user)
):
    """List tags"""
    db = ad.common.get_async_db()
    # Get total count
    total_count = await db.tags.count_documents({"organization_id": organization_id})
    
    # Build base query with optional name search
    tags_query = {"organization_id": organization_id}
    if name_search:
        tags_query["name"] = {"$regex": name_search, "$options": "i"}

    # Get paginated tags with sorting by _id in descending order
    cursor = db.tags.find(tags_query).sort("_id", -1).skip(skip).limit(limit)
    
    tags = await cursor.to_list(length=None)
    
    return ListTagsResponse(
        tags=[
            {
                "id": str(tag["_id"]),
                "name": tag["name"],
                "color": tag.get("color"),
                "description": tag.get("description"),
                "created_at": tag["created_at"],
                "created_by": tag["created_by"]
            }
            for tag in tags
        ],
        total_count=total_count,
        skip=skip
    )

@tags_router.delete("/v0/orgs/{organization_id}/tags/{tag_id}")
async def delete_tag(
    organization_id: str,
    tag_id: str,
    current_user: User = Depends(get_org_user)
):
    """Delete a tag"""
    db = ad.common.get_async_db()
    # Verify tag exists and belongs to user
    tag = await db.tags.find_one({
        "_id": ObjectId(tag_id),
        "organization_id": organization_id
    })
    
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    # Check if tag is used in any documents
    documents_with_tag = await db.docs.find_one({
        "tag_ids": tag_id
    })
    
    if documents_with_tag:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete tag '{tag['name']}' because it is assigned to one or more documents"
        )

    # Check if tag is used in any prompts
    prompts_with_tag = await db.prompt_revisions.find_one({
        "tag_ids": tag_id
    })
    
    if prompts_with_tag:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete tag '{tag['name']}' because it is assigned to one or more prompts"
        )
    
    result = await db.tags.delete_one({
        "_id": ObjectId(tag_id),
        "organization_id": organization_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    return {"message": "Tag deleted successfully"}

@tags_router.put("/v0/orgs/{organization_id}/tags/{tag_id}", response_model=Tag)
async def update_tag(
    organization_id: str,
    tag_id: str,
    tag: TagConfig,
    current_user: User = Depends(get_org_user)
):
    """Update a tag"""
    db = ad.common.get_async_db()
    
    # Verify tag exists and belongs to user
    existing_tag = await db.tags.find_one({
        "_id": ObjectId(tag_id),
        "organization_id": organization_id
    })
    
    if not existing_tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    # Update all fields including name
    update_data = {
        "name": tag.name,
        "color": tag.color,
        "description": tag.description
    }
    
    updated_tag = await db.tags.find_one_and_update(
        {"_id": ObjectId(tag_id)},
        {"$set": update_data},
        return_document=True
    )
    
    if not updated_tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    return Tag(**{**updated_tag, "id": str(updated_tag["_id"])})

@tags_router.get("/v0/orgs/{organization_id}/tags/{tag_id}", response_model=Tag)
async def get_tag(
    organization_id: str,
    tag_id: str,
    current_user: User = Depends(get_org_user)
):
    """Get a tag by ID"""
    db = ad.common.get_async_db()
    tag = await db.tags.find_one({
        "_id": ObjectId(tag_id),
        "organization_id": organization_id
    })
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return Tag(**{**tag, "id": str(tag["_id"])})
