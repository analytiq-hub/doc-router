from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, UTC
from bson import ObjectId

import analytiq_data as ad
from setup import get_async_db
from auth import get_current_user
from schemas import (
    Prompt,
    PromptCreate,
    ListPromptsResponse,
    User
)

prompts_router = APIRouter(
    prefix="/prompts",
    tags=["prompts"]
)

async def get_next_prompt_version(prompt_name: str) -> int:
    """Atomically get the next version number for a prompt"""
    db = get_async_db()
    result = await db.prompt_versions.find_one_and_update(
        {"_id": prompt_name},
        {"$inc": {"version": 1}},
        upsert=True,
        return_document=True
    )
    return result["version"]

@prompts_router.post("", response_model=Prompt)
async def create_prompt(
    prompt: PromptCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a prompt"""
    db = get_async_db()
    
    # Only verify schema if one is specified
    if prompt.schema_name and prompt.schema_version:
        schema = await db.schemas.find_one({
            "name": prompt.schema_name,
            "version": prompt.schema_version
        })
        if not schema:
            raise HTTPException(
                status_code=404,
                detail=f"Schema {prompt.schema_name} version {prompt.schema_version} not found"
            )

    # Validate tag IDs if provided
    if prompt.tag_ids:
        tags_cursor = db.tags.find({
            "_id": {"$in": [ObjectId(tag_id) for tag_id in prompt.tag_ids]},
            "created_by": current_user.user_id
        })
        existing_tags = await tags_cursor.to_list(None)
        existing_tag_ids = {str(tag["_id"]) for tag in existing_tags}
        
        invalid_tags = set(prompt.tag_ids) - existing_tag_ids
        if invalid_tags:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tag IDs: {list(invalid_tags)}"
            )

    # Check if prompt with this name already exists (case-insensitive)
    existing_prompt = await db.prompts.find_one({
        "name": {"$regex": f"^{prompt.name}$", "$options": "i"}
    })
    
    # Get the next version
    new_version = await get_next_prompt_version(prompt.name)
    
    # Create prompt document
    prompt_dict = {
        "name": existing_prompt["name"] if existing_prompt else prompt.name,
        "content": prompt.content,
        "schema_name": prompt.schema_name or "",
        "schema_version": prompt.schema_version or 0,
        "version": new_version,
        "created_at": datetime.utcnow(),
        "created_by": current_user.user_id,
        "tag_ids": prompt.tag_ids
    }
    
    # Insert into MongoDB
    result = await db.prompts.insert_one(prompt_dict)
    
    # Return complete prompt
    prompt_dict["id"] = str(result.inserted_id)
    return Prompt(**prompt_dict)

@prompts_router.get("", response_model=ListPromptsResponse)
async def list_prompts(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    document_id: str = Query(None, description="Filter prompts by document's tags"),
    tag_ids: str = Query(None, description="Comma-separated list of tag IDs"),
    current_user: User = Depends(get_current_user)
):
    """List prompts"""
    db = get_async_db()
    
    # Build the base pipeline
    pipeline = []
    
    # Add document tag filtering if document_id is provided
    if document_id:
        document = await db.docs.find_one({"_id": ObjectId(document_id)})
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document_tag_ids = document.get("tag_ids", [])
        if document_tag_ids:
            pipeline.append({
                "$match": {"tag_ids": {"$in": document_tag_ids}}
            })
    # Add direct tag filtering if tag_ids are provided
    elif tag_ids:
        tag_id_list = [tid.strip() for tid in tag_ids.split(",")]
        pipeline.append({
            "$match": {"tag_ids": {"$all": tag_id_list}}
        })
    
    # Add the rest of the pipeline stages
    pipeline.extend([
        {
            "$sort": {"_id": -1}
        },
        {
            "$group": {
                "_id": "$name",
                "doc": {"$first": "$$ROOT"}
            }
        },
        {
            "$replaceRoot": {"newRoot": "$doc"}
        },
        {
            "$sort": {"_id": -1}
        },
        {
            "$facet": {
                "total": [{"$count": "count"}],
                "prompts": [
                    {"$skip": skip},
                    {"$limit": limit}
                ]
            }
        }
    ])
    
    result = await db.prompts.aggregate(pipeline).to_list(length=1)
    result = result[0]
    
    total_count = result["total"][0]["count"] if result["total"] else 0
    prompts = result["prompts"]
    
    # Convert _id to id in each prompt
    for prompt in prompts:
        prompt['id'] = str(prompt.pop('_id'))
    
    return ListPromptsResponse(
        prompts=prompts,
        total_count=total_count,
        skip=skip
    )

@prompts_router.get("/{prompt_id}", response_model=Prompt)
async def get_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a prompt"""
    db = get_async_db()
    
    prompt = await db.prompts.find_one({"_id": ObjectId(prompt_id)})
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    prompt['id'] = str(prompt.pop('_id'))
    return Prompt(**prompt)

@prompts_router.put("/{prompt_id}", response_model=Prompt)
async def update_prompt(
    prompt_id: str,
    prompt: PromptCreate,
    current_user: User = Depends(get_current_user)
):
    """Update a prompt"""
    db = get_async_db()
    
    # Get the existing prompt
    existing_prompt = await db.prompts.find_one({"_id": ObjectId(prompt_id)})
    if not existing_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # Check if user has permission to update
    if existing_prompt["created_by"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this prompt")
    
    # Only verify schema if one is specified
    if prompt.schema_name and prompt.schema_version:
        schema = await db.schemas.find_one({
            "name": prompt.schema_name,
            "version": prompt.schema_version
        })
        if not schema:
            raise HTTPException(
                status_code=404,
                detail=f"Schema {prompt.schema_name} version {prompt.schema_version} not found"
            )
    
    # Validate tag IDs if provided
    if prompt.tag_ids:
        tags_cursor = db.tags.find({
            "_id": {"$in": [ObjectId(tag_id) for tag_id in prompt.tag_ids]},
            "created_by": current_user.user_id
        })
        existing_tags = await tags_cursor.to_list(None)
        existing_tag_ids = {str(tag["_id"]) for tag in existing_tags}
        
        invalid_tags = set(prompt.tag_ids) - existing_tag_ids
        if invalid_tags:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tag IDs: {list(invalid_tags)}"
            )
    
    # Get the next version number
    new_version = await get_next_prompt_version(existing_prompt["name"])
    
    # Create new version of the prompt
    new_prompt = {
        "name": prompt.name,
        "content": prompt.content,
        "schema_name": prompt.schema_name or "",  # Use empty string if None
        "schema_version": prompt.schema_version or 0,  # Use 0 if None
        "version": new_version,
        "created_at": datetime.utcnow(),
        "created_by": current_user.user_id,
        "tag_ids": prompt.tag_ids
    }
    
    # Insert new version
    result = await db.prompts.insert_one(new_prompt)
    
    # Return updated prompt
    new_prompt["id"] = str(result.inserted_id)
    return Prompt(**new_prompt)

@prompts_router.delete("/{prompt_id}")
async def delete_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a prompt"""
    db = get_async_db()
    
    # Get the prompt to find its name
    prompt = await db.prompts.find_one({"_id": ObjectId(prompt_id)})
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    if prompt["created_by"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this prompt")
    
    # Delete all versions of this prompt
    result = await db.prompts.delete_many({"name": prompt["name"]})
    
    # Also delete the version counter
    await db.prompt_versions.delete_one({"_id": prompt["name"]})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"message": "Prompt deleted successfully"} 