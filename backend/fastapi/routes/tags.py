from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, UTC
from bson import ObjectId

import analytiq_data as ad
from setup import get_async_db
from auth import get_current_user
from schemas import (
    Tag,
    TagCreate,
    ListTagsResponse,
    User
)

tags_router = APIRouter(
    prefix="/tags",
    tags=["tags"]
)

@tags_router.post("", response_model=Tag)
async def create_tag(
    tag: TagCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a tag"""
    db = get_async_db()
    
    # Check if tag with this name already exists for this user
    existing_tag = await db.tags.find_one({
        "name": tag.name,
        "created_by": current_user.user_id
    })
    
    if existing_tag:
        raise HTTPException(
            status_code=400,
            detail=f"Tag with name '{tag.name}' already exists"
        )
    
    # Create tag document
    tag_dict = {
        "name": tag.name,
        "color": tag.color,
        "description": tag.description,
        "created_at": datetime.utcnow(),
        "created_by": current_user.user_id
    }
    
    # Insert into MongoDB
    result = await db.tags.insert_one(tag_dict)
    
    # Return complete tag
    tag_dict["id"] = str(result.inserted_id)
    return Tag(**tag_dict)

@tags_router.get("", response_model=ListTagsResponse)
async def list_tags(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """List tags"""
    db = get_async_db()
    
    # Get total count
    total_count = await db.tags.count_documents({
        "created_by": current_user.user_id
    })
    
    # Get paginated tags
    cursor = db.tags.find({
        "created_by": current_user.user_id
    }).sort("_id", -1).skip(skip).limit(limit)
    
    tags = await cursor.to_list(None)
    
    # Convert _id to id in each tag
    for tag in tags:
        tag['id'] = str(tag.pop('_id'))
    
    return ListTagsResponse(
        tags=tags,
        total_count=total_count,
        skip=skip
    )

@tags_router.get("/{tag_id}", response_model=Tag)
async def get_tag(
    tag_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a tag"""
    db = get_async_db()
    
    tag = await db.tags.find_one({
        "_id": ObjectId(tag_id),
        "created_by": current_user.user_id
    })
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag['id'] = str(tag.pop('_id'))
    return Tag(**tag)

@tags_router.put("/{tag_id}", response_model=Tag)
async def update_tag(
    tag_id: str,
    tag: TagCreate,
    current_user: User = Depends(get_current_user)
):
    """Update a tag"""
    db = get_async_db()
    
    # Check if tag exists and user has permission
    existing_tag = await db.tags.find_one({
        "_id": ObjectId(tag_id),
        "created_by": current_user.user_id
    })
    if not existing_tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    # Check if new name conflicts with existing tag
    if tag.name != existing_tag["name"]:
        name_conflict = await db.tags.find_one({
            "name": tag.name,
            "created_by": current_user.user_id,
            "_id": {"$ne": ObjectId(tag_id)}
        })
        if name_conflict:
            raise HTTPException(
                status_code=400,
                detail=f"Tag with name '{tag.name}' already exists"
            )
    
    # Update tag
    update_data = {
        "name": tag.name,
        "color": tag.color,
        "description": tag.description
    }
    
    result = await db.tags.find_one_and_update(
        {"_id": ObjectId(tag_id)},
        {"$set": update_data},
        return_document=True
    )
    
    result["id"] = str(result.pop("_id"))
    return Tag(**result)

@tags_router.delete("/{tag_id}")
async def delete_tag(
    tag_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a tag"""
    db = get_async_db()
    
    # Check if tag exists and user has permission
    tag = await db.tags.find_one({
        "_id": ObjectId(tag_id),
        "created_by": current_user.user_id
    })
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    # Check if tag is in use
    doc_with_tag = await db.docs.find_one({"tag_ids": tag_id})
    if doc_with_tag:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete tag that is still in use by documents"
        )
    
    # Delete tag
    result = await db.tags.delete_one({
        "_id": ObjectId(tag_id),
        "created_by": current_user.user_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"message": "Tag deleted successfully"} 