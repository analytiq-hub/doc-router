# prompts.py

# Standard library imports
import json
import logging
from datetime import datetime, UTC
from typing import Optional, List, Literal, Dict
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from bson import ObjectId

# Local imports
import analytiq_data as ad
from analytiq_data.common.prompt_list import list_prompts_for_org
from app.auth import get_org_user
from app.models import User

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
prompts_router = APIRouter(tags=["prompts"])

# Prompt models
class IncludeConfig(BaseModel):
    """
    Controls which parts of each document are included in the generated LLM context.

    Defaults preserve existing single-document behavior.
    """
    ocr_text: bool = True
    metadata_keys: List[str] = []
    pdf: bool = True


class PromptConfig(BaseModel):
    name: str
    content: str
    schema_id: Optional[str] = None
    schema_version: Optional[int] = None
    tag_ids: List[str] = []
    model: str = "gpt-4o-mini"
    kb_id: Optional[str] = None  # Optional knowledge base ID for RAG
    # Grouped peer prompt fields (see docs/plan-prompt-group-by.md)
    peer_match_keys: List[str] = []
    include: IncludeConfig = IncludeConfig()


# Cache the expected default include config.
# We use a constant here to avoid "default divergence" if IncludeConfig defaults
# change later (old DB documents without `include` should not suddenly compare
# unequal and trigger spurious new revisions).
DEFAULT_INCLUDE_DUMP: Dict[str, object] = IncludeConfig().model_dump()


class Prompt(PromptConfig):
    prompt_revid: str           # MongoDB's _id
    prompt_id: str    # Stable identifier
    prompt_version: int
    created_at: datetime
    created_by: str

class ListPromptsResponse(BaseModel):
    prompts: List[Prompt]
    total_count: int
    skip: int

# Helper functions
async def get_prompt_id_and_version(prompt_id: Optional[str] = None) -> tuple[str, int]:
    """
    Get the next version for an existing prompt or create a new prompt identifier.
    
    Args:
        prompt_id: Existing prompt ID, or None to create a new one
        
    Returns:
        Tuple of (prompt_id, prompt_version)
    """
    db = ad.common.get_async_db()

    if prompt_id is None:
        # Insert a placeholder document to get MongoDB-generated ID
        result = await db.prompts.insert_one({
            "prompt_version": 1
        })
        
        # Use the MongoDB-assigned _id as our prompt_id
        prompt_id = str(result.inserted_id)
        prompt_version = 1
    else:
        # Get the next version for an existing prompt
        result = await db.prompts.find_one_and_update(
            {"_id": ObjectId(prompt_id)},
            {"$inc": {"prompt_version": 1}},
            upsert=True,
            return_document=True
        )
        prompt_version = result["prompt_version"]
    
    return prompt_id, prompt_version

async def validate_and_resolve_schema(prompt: PromptConfig) -> Optional[dict]:
    """
    Validate and resolve schema information for a prompt.
    
    If schema_id is provided:
    - If schema_version is also provided, validates that specific version exists
    - If schema_version is None, auto-fetches the latest version and updates the prompt
    
    Args:
        prompt: The prompt configuration to validate
        
    Returns:
        The schema document if found, None if no schema_id provided
        
    Raises:
        HTTPException: If schema_id is provided but schema not found
    """
    if not prompt.schema_id:
        return None
        
    db = ad.common.get_async_db()
    
    if prompt.schema_version:
        # Both schema_id and schema_version provided - verify specific version
        schema = await db.schema_revisions.find_one({
            "schema_id": prompt.schema_id,
            "schema_version": prompt.schema_version,
        })
        if not schema:
            raise HTTPException(
                status_code=404,
                detail=f"Schema with ID {prompt.schema_id} version {prompt.schema_version} not found"
            )
    else:
        # Only schema_id provided - auto-fetch latest version
        schema = await db.schema_revisions.find_one(
            {"schema_id": prompt.schema_id},
            sort=[("schema_version", -1)]  # Get highest version
        )
        if not schema:
            raise HTTPException(
                status_code=404,
                detail=f"Schema with ID {prompt.schema_id} not found"
            )
        # Update the prompt with the latest schema version
        prompt.schema_version = schema["schema_version"]
    
    return schema

# Prompt management endpoints
@prompts_router.post("/v0/orgs/{organization_id}/prompts", response_model=Prompt)
async def create_prompt(
    organization_id: str,
    prompt: PromptConfig,
    current_user: User = Depends(get_org_user)
):
    """Create a prompt"""
    logger.info(f"create_prompt() start: organization_id: {organization_id}, prompt: {prompt}")
    db = ad.common.get_async_db()

    # Verify schema if specified
    schema = await validate_and_resolve_schema(prompt)

    # Validate model exists
    found = False
    for provider in await db.llm_providers.find({}).to_list(None):
        if prompt.model in provider["litellm_models_enabled"]:
            found = True
            break
    if not found:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model: {prompt.model}"
        )

    # Validate tag IDs if provided
    if prompt.tag_ids:
        tags_cursor = db.tags.find({
            "_id": {"$in": [ObjectId(tag_id) for tag_id in prompt.tag_ids]},
            "organization_id": organization_id
        })
        existing_tags = await tags_cursor.to_list(None)
        existing_tag_ids = {str(tag["_id"]) for tag in existing_tags}
        
        invalid_tags = set(prompt.tag_ids) - existing_tag_ids
        if invalid_tags:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tag IDs: {list(invalid_tags)}"
            )
        # Only set schema_id if schema exists and was verified above
        if prompt.schema_id and 'schema' in locals():
            prompt.schema_id = schema["schema_id"]

    prompt_name = prompt.name

    # Does the prompt name already exist?
    existing_prompt = await db.prompts.find_one({
        "name": prompt_name,
        "organization_id": organization_id
    })

    if existing_prompt:
        # `db.prompts` documents are keyed by their Mongo `_id` (stable prompt id).
        # On name collisions we must increment the existing prompt_version for that same stable id.
        prompt_id, new_prompt_version = await get_prompt_id_and_version(str(existing_prompt["_id"]))
    else:
        prompt_id, new_prompt_version = await get_prompt_id_and_version(None)
    
    # Update the prompts collection with name and organization_id
    await db.prompts.update_one(
        {"_id": ObjectId(prompt_id)},
        {"$set": {
            "name": prompt.name,
            "organization_id": organization_id
        }},
        upsert=True
    )
    
    # Validate kb_id if provided
    if prompt.kb_id:
        # Verify KB exists and belongs to org
        kb = await db.knowledge_bases.find_one({
            "_id": ObjectId(prompt.kb_id),
            "organization_id": organization_id
        })
        if not kb:
            raise HTTPException(
                status_code=400,
                detail=f"Knowledge base {prompt.kb_id} not found or not accessible"
            )
        if kb.get("status") != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Knowledge base {prompt.kb_id} is not active (status: {kb.get('status')})"
            )
    
    # Create prompt document for prompt_revisions
    prompt_dict = {
        "prompt_id": prompt_id,  # Add stable identifier
        "content": prompt.content,
        "schema_id": prompt.schema_id,
        "schema_version": prompt.schema_version,
        "prompt_version": new_prompt_version,
        "created_at": datetime.now(UTC),
        "created_by": current_user.user_id,
        "tag_ids": prompt.tag_ids,
        "model": prompt.model,
        "organization_id": organization_id,
        "kb_id": prompt.kb_id,  # Store KB ID for RAG
        # Grouped peer fields
        "peer_match_keys": prompt.peer_match_keys or [],
        "include": prompt.include.model_dump() if prompt.include else DEFAULT_INCLUDE_DUMP,
    }
    
    # Insert into MongoDB
    result = await db.prompt_revisions.insert_one(prompt_dict)
    
    # Return complete prompt, adding name from prompts collection
    prompt_dict["name"] = prompt.name
    prompt_dict["prompt_revid"] = str(result.inserted_id)
    return Prompt(**prompt_dict)

@prompts_router.get("/v0/orgs/{organization_id}/prompts", response_model=ListPromptsResponse)
async def list_prompts(
    organization_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    document_id: str = Query(None, description="Filter prompts by document's tags"),
    tag_ids: str = Query(None, description="Comma-separated list of tag IDs"),
    name_search: str = Query(None, description="Search term for prompt names"),
    sort: str = Query(None, description="JSON-encoded MUI DataGrid sortModel (array)."),
    filters: str = Query(None, description="JSON-encoded MUI DataGrid filterModel (object)."),
    current_user: User = Depends(get_org_user)
):
    """List prompts within an organization"""
    sort_model = None
    filter_model = None
    if sort:
        try:
            sort_model = json.loads(sort)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid sort JSON")
    if filters:
        try:
            filter_model = json.loads(filters)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid filters JSON")

    logger.info(
        f"list_prompts(): org={organization_id} skip={skip} limit={limit} "
        f"document_id={document_id} tag_ids={tag_ids} name_search={name_search} "
        f"sort_model={sort_model} filter_model={filter_model}"
    )
    db = ad.common.get_async_db()

    tag_id_list = [tid.strip() for tid in tag_ids.split(",")] if tag_ids else None

    pre_grid_stages: list[dict] = []
    if document_id:
        document = await db.docs.find_one(
            {
                "_id": ObjectId(document_id),
                "organization_id": organization_id,
            }
        )
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        default_prompt_enabled = True
        try:
            org = await db.organizations.find_one({"_id": ObjectId(organization_id)})
            if org is not None:
                default_prompt_enabled = org.get("default_prompt_enabled", True)
        except Exception as e:
            logger.warning(
                "Could not load organization %s for default_prompt_enabled while listing prompts; "
                "falling back to enabled. Error: %s",
                organization_id,
                e,
            )

        document_tag_ids = document.get("tag_ids", [])
        if document_tag_ids:
            pre_grid_stages.append({"$match": {"tag_ids": {"$in": document_tag_ids}}})
        else:
            pre_grid_stages.append(
                {
                    "$match": (
                        {"name": "Default Prompt"}
                        if default_prompt_enabled
                        else {"_id": {"$exists": False}}
                    )
                }
            )

    prompts, total_count = await list_prompts_for_org(
        db,
        organization_id,
        skip=skip,
        limit=limit,
        name_search=name_search,
        tag_ids_param=tag_id_list,
        sort_model=sort_model,
        filter_model=filter_model,
        pre_grid_stages=pre_grid_stages or None,
    )

    return ListPromptsResponse(
        prompts=prompts,
        total_count=total_count,
        skip=skip,
    )

@prompts_router.get("/v0/orgs/{organization_id}/prompts/{prompt_revid}", response_model=Prompt)
async def get_prompt(
    organization_id: str,
    prompt_revid: str,
    current_user: User = Depends(get_org_user)
):
    """Get a prompt"""
    logger.info(f"get_prompt() start: organization_id: {organization_id}, prompt_revid: {prompt_revid}")
    db = ad.common.get_async_db()
    
    # Get the prompt revision
    revision = await db.prompt_revisions.find_one({
        "_id": ObjectId(prompt_revid)
    })
    if not revision:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # Get the prompt name and verify organization
    prompt = await db.prompts.find_one({
        "_id": ObjectId(revision["prompt_id"]),
        "organization_id": organization_id
    })
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found or not in this organization")
    
    # Combine the data
    revision['prompt_revid'] = str(revision.pop('_id'))
    revision['name'] = prompt['name']
    
    return Prompt(**revision)

@prompts_router.put("/v0/orgs/{organization_id}/prompts/{prompt_id}", response_model=Prompt)
async def update_prompt(
    organization_id: str,
    prompt_id: str,
    prompt: PromptConfig,
    current_user: User = Depends(get_org_user)
):
    """Update a prompt"""
    logger.info(f"update_prompt() start: organization_id: {organization_id}, prompt_id: {prompt_id}")
    db = ad.common.get_async_db()

    # Check if the prompt exists
    existing_prompt = await db.prompts.find_one({
        "_id": ObjectId(prompt_id),
        "organization_id": organization_id
    })
    if not existing_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # Only verify schema if one is specified
    schema = await validate_and_resolve_schema(prompt)

    # Validate model exists
    found = False
    for provider in await db.llm_providers.find({}).to_list(None):
        if prompt.model in provider["litellm_models_enabled"]:
            found = True
            break
    if not found:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model: {prompt.model}"
        )
    
    # Validate tag IDs if provided
    if prompt.tag_ids:
        tags_cursor = db.tags.find({
            "_id": {"$in": [ObjectId(tag_id) for tag_id in prompt.tag_ids]},
            "organization_id": organization_id
        })
        existing_tags = await tags_cursor.to_list(None)
        existing_tag_ids = {str(tag["_id"]) for tag in existing_tags}
        
        invalid_tags = set(prompt.tag_ids) - existing_tag_ids
        if invalid_tags:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tag IDs: {list(invalid_tags)}"
            ) 

    # Get the latest prompt revision
    latest_prompt_revision = await db.prompt_revisions.find_one(
        {"prompt_id": prompt_id},
        sort=[("prompt_version", -1)]
    )
    if not latest_prompt_revision:
        raise HTTPException(status_code=404, detail="Prompt not found or not in this organization")

    # Check if only the name has changed
    only_name_changed = (
        prompt.name != existing_prompt["name"] and
        prompt.content == latest_prompt_revision["content"] and
        prompt.schema_id == latest_prompt_revision.get("schema_id") and
        prompt.schema_version == latest_prompt_revision.get("schema_version") and
        prompt.model == latest_prompt_revision["model"] and
        set(prompt.tag_ids or []) == set(latest_prompt_revision.get("tag_ids") or []) and
        (prompt.peer_match_keys or []) == latest_prompt_revision.get("peer_match_keys", []) and
        (prompt.include.model_dump() if prompt.include else DEFAULT_INCLUDE_DUMP)
        == latest_prompt_revision.get("include", DEFAULT_INCLUDE_DUMP)
    )
    
    if prompt.name != existing_prompt["name"]:
        # Update the name in the prompts collection
        result = await db.prompts.update_one(
            {"_id": ObjectId(prompt_id)},
            {"$set": {"name": prompt.name}}
        )

        if only_name_changed:
            if result.modified_count > 0:
                # Return the updated prompt
                updated_revision = latest_prompt_revision.copy()
                updated_revision["prompt_revid"] = str(updated_revision.pop("_id"))
                updated_revision["name"] = prompt.name
                return Prompt(**updated_revision)
            else:
                raise HTTPException(status_code=500, detail="Failed to update prompt name")
    
    # If other fields changed, create a new version
    # Get the next version number using the stable prompt_id
    _, new_prompt_version = await get_prompt_id_and_version(prompt_id)
    
    # Create new version of the prompt in prompt_revisions
    new_prompt = {
        "prompt_id": prompt_id,  # Preserve stable identifier
        "content": prompt.content,
        "schema_id": prompt.schema_id,
        "schema_version": prompt.schema_version,
        "prompt_version": new_prompt_version,
        "created_at": datetime.now(UTC),
        "created_by": current_user.user_id,
        "tag_ids": prompt.tag_ids,
        "model": prompt.model,
        "organization_id": organization_id,
        "kb_id": prompt.kb_id,  # Store KB ID for RAG
        # Grouped peer fields
        "peer_match_keys": prompt.peer_match_keys or [],
        "include": prompt.include.model_dump() if prompt.include else DEFAULT_INCLUDE_DUMP,
    }
    
    # Insert new version
    result = await db.prompt_revisions.insert_one(new_prompt)
    
    # Return updated prompt
    new_prompt["prompt_revid"] = str(result.inserted_id)
    new_prompt["name"] = prompt.name  # Add name from the prompts collection
    return Prompt(**new_prompt)

@prompts_router.delete("/v0/orgs/{organization_id}/prompts/{prompt_id}")
async def delete_prompt(
    organization_id: str,
    prompt_id: str,
    current_user: User = Depends(get_org_user)
):
    """Delete a prompt"""
    logger.info(f"delete_prompt() start: organization_id: {organization_id}, prompt_id: {prompt_id}")
    db = ad.common.get_async_db()
    
    # Get the prompt revision   
    prompt_revision = await db.prompt_revisions.find_one({
        "prompt_id": prompt_id
    })
    if not prompt_revision:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # Get the prompt and verify organization
    prompt = await db.prompts.find_one({
        "_id": ObjectId(prompt_id),
        "organization_id": organization_id
    })
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found or not in this organization")
  
    # Delete all revisions of this prompt
    result = await db.prompt_revisions.delete_many({
        "prompt_id": prompt_id
    })
    
    # Delete the prompt entry
    await db.prompts.delete_one({"_id": ObjectId(prompt_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No prompt revisions found")
        
    return {"message": "Prompt deleted successfully"}

@prompts_router.get("/v0/orgs/{organization_id}/prompts/{prompt_id}/versions", response_model=ListPromptsResponse)
async def list_prompt_versions(
    organization_id: str,
    prompt_id: str,
    current_user: User = Depends(get_org_user)
):
    """List all versions of a prompt by prompt_id"""
    logger.info(f"list_prompt_versions() start: organization_id: {organization_id}, prompt_id: {prompt_id}")
    db = ad.common.get_async_db()
    
    # Verify the prompt belongs to the organization
    prompt = await db.prompts.find_one({
        "_id": ObjectId(prompt_id),
        "organization_id": organization_id
    })
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found or not in this organization")
    
    # Get all revisions for this prompt_id, sorted by version descending
    revisions = await db.prompt_revisions.find(
        {"prompt_id": prompt_id}
    ).sort("prompt_version", -1).to_list(None)
    
    if not revisions:
        return ListPromptsResponse(prompts=[], total_count=0, skip=0)
    
    # Convert _id to prompt_revid and add name
    for revision in revisions:
        revision['prompt_revid'] = str(revision.pop('_id'))
        revision['name'] = prompt['name']
    
    return ListPromptsResponse(
        prompts=revisions,
        total_count=len(revisions),
        skip=0
    )
