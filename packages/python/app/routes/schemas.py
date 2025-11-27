# schemas.py

# Standard library imports
import json
import logging
from datetime import datetime, UTC
from typing import Optional, List, Literal, Dict, ForwardRef
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from bson import ObjectId
from jsonschema import Draft7Validator

# Local imports
import analytiq_data as ad
from app.auth import get_org_user
from app.models import User

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
schemas_router = APIRouter(tags=["schemas"])

# Schema models
class SchemaProperty(BaseModel):
    type: Literal['string', 'integer', 'number', 'boolean', 'array', 'object']
    format: str | None = None
    description: str | None = None
    items: ForwardRef('SchemaProperty') | None = None
    properties: Dict[str, ForwardRef('SchemaProperty')] | None = None

class SchemaResponseFormat(BaseModel):
    type: Literal['json_schema']
    json_schema: dict = Field(
        ...,
        description="JSON schema definition following OpenAI format"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "json_schema",
                "json_schema": {
                    "name": "extract_person_info",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                            "email": {"type": "string", "format": "email"}
                        },
                        "required": ["name", "age"]
                    }
                }
            }
        }
    )
    
    @field_validator('json_schema')
    def validate_json_schema(cls, v):
        # Validate schema follows OpenAI format
        if not isinstance(v, dict):
            raise ValueError("json_schema must be a dictionary")
        
        required_fields = ['name', 'schema']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"json_schema must contain '{field}' field")
        
        # Validate the actual JSON schema
        try:
            Draft7Validator.check_schema(v['schema'])
        except Exception as e:
            raise ValueError(f"Invalid JSON schema: {str(e)}")
        
        return v

class SchemaConfig(BaseModel):
    name: str
    response_format: SchemaResponseFormat

class Schema(SchemaConfig):
    schema_revid: str # MongoDB's _id
    schema_id: str    # Stable identifier
    schema_version: int
    created_at: datetime
    created_by: str

class ListSchemasResponse(BaseModel):
    schemas: List[Schema]
    total_count: int
    skip: int

# Helper functions
async def get_schema_id_and_version(schema_id: Optional[str] = None) -> tuple[str, int]:
    """
    Get the next version for an existing schema or create a new schema identifier.
    
    Args:
        schema_id: Existing schema ID, or None to create a new one
        
    Returns:
        Tuple of (schema_id, schema_version)
    """
    db = ad.common.get_async_db()

    if schema_id is None:
        # Insert a placeholder document to get MongoDB-generated ID
        result = await db.schemas.insert_one({
            "schema_version": 1
        })
        
        # Use the MongoDB-assigned _id as our schema_id
        schema_id = str(result.inserted_id)
        schema_version = 1
    else:
        # Get the next version for an existing schema
        result = await db.schemas.find_one_and_update(
            {"_id": ObjectId(schema_id)},
            {"$inc": {"schema_version": 1}},
            upsert=True,
            return_document=True
        )
        schema_version = result["schema_version"]
    
    return schema_id, schema_version

def validate_schema_fields(fields: list) -> tuple[bool, str]:
    field_names = [field.name.lower() for field in fields]
    seen = set()
    for name in field_names:
        if name in seen:
            return False, f"Duplicate field name: {name}"
        seen.add(name)
    return True, ""

# Schema management endpoints
@schemas_router.post("/v0/orgs/{organization_id}/schemas", response_model=Schema)
async def create_schema(
    organization_id: str,
    schema: SchemaConfig,
    current_user: User = Depends(get_org_user)
):
    """Create a schema"""
    logger.info(f"create_schema() start: organization_id: {organization_id}, schema: {schema}")
    db = ad.common.get_async_db()

    # Check if schema with this name already exists (case-insensitive)
    existing_schema = await db.schemas.find_one({
        "name": {"$regex": f"^{schema.name}$", "$options": "i"},
        "organization_id": organization_id
    })

    # Generate schema_id and version
    if existing_schema:
        schema_id, new_schema_version = await get_schema_id_and_version(str(existing_schema["_id"]))
    else:
        # Generate a new schema_id when creating a new schema
        schema_id, new_schema_version = await get_schema_id_and_version(None)
    
    # Update the schemas collection with name and organization_id
    await db.schemas.update_one(
        {"_id": ObjectId(schema_id)},
        {"$set": {
            "name": schema.name,
            "organization_id": organization_id
        }},
        upsert=True
    )
    
    # Create schema document for schema_revisions
    schema_dict = {
        "schema_id": schema_id,
        "response_format": schema.response_format.model_dump(),
        "schema_version": new_schema_version,
        "created_at": datetime.now(UTC),
        "created_by": current_user.user_id
    }
    
    # Insert into MongoDB
    result = await db.schema_revisions.insert_one(schema_dict)
    
    # Return complete schema
    schema_dict["name"] = schema.name
    schema_dict["schema_revid"] = str(result.inserted_id)
    return Schema(**schema_dict)

@schemas_router.get("/v0/orgs/{organization_id}/schemas", response_model=ListSchemasResponse)
async def list_schemas(
    organization_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    name_search: str = Query(None, description="Search term for schema names"),
    current_user: User = Depends(get_org_user)
):
    """List latest schema revisions within an organization"""
    logger.info(f"list_schemas() start: organization_id: {organization_id}, skip: {skip}, limit: {limit}")
    db = ad.common.get_async_db()
    
    # First, get schemas that belong to the organization
    # Build base query for schemas in org
    schemas_query = {"organization_id": organization_id}
    # Optional name search (case-insensitive)
    if name_search:
        schemas_query["name"] = {"$regex": name_search, "$options": "i"}

    org_schemas = await db.schemas.find(schemas_query).to_list(None)
    
    if not org_schemas:
        return ListSchemasResponse(schemas=[], total_count=0, skip=skip)
    
    # Extract schema IDs (restricted to name_search if provided)
    schema_ids = [schema["_id"] for schema in org_schemas]
    schema_id_to_name = {str(schema["_id"]): schema["name"] for schema in org_schemas}
    
    # Build pipeline for schema_revisions
    pipeline = [
        {
            "$match": {"schema_id": {"$in": [str(sid) for sid in schema_ids]}}
        },
        {
            "$sort": {"_id": -1}
        },
        {
            "$group": {
                "_id": "$schema_id",
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
                "schemas": [
                    {"$skip": skip},
                    {"$limit": limit}
                ]
            }
        }
    ]
    
    result = await db.schema_revisions.aggregate(pipeline).to_list(length=1)
    result = result[0]
    
    total_count = result["total"][0]["count"] if result["total"] else 0
    schemas = result["schemas"]
    
    # Convert _id to id in each schema and add name from schemas collection
    for schema in schemas:
        schema['schema_revid'] = str(schema.pop('_id'))
        schema['name'] = schema_id_to_name.get(schema['schema_id'], "Unknown")
    
    return ListSchemasResponse(
        schemas=schemas,
        total_count=total_count,
        skip=skip
    )

@schemas_router.get("/v0/orgs/{organization_id}/schemas/{schema_revid}", response_model=Schema)
async def get_schema(
    organization_id: str,
    schema_revid: str,
    current_user: User = Depends(get_org_user)
):
    """Get a schema revision"""
    logger.info(f"get_schema() start: organization_id: {organization_id}, schema_revid: {schema_revid}")
    db = ad.common.get_async_db()
    
    # Get the schema revision
    revision = await db.schema_revisions.find_one({
        "_id": ObjectId(schema_revid)
    })
    if not revision:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    # Get the schema name and verify organization
    schema = await db.schemas.find_one({
        "_id": ObjectId(revision["schema_id"]),
        "organization_id": organization_id
    })
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found or not in this organization")
    
    # Combine the data
    revision['schema_revid'] = str(revision.pop('_id'))
    revision['name'] = schema['name']
    
    return Schema(**revision)

@schemas_router.put("/v0/orgs/{organization_id}/schemas/{schema_id}", response_model=Schema)
async def update_schema(
    organization_id: str,
    schema_id: str,
    schema: SchemaConfig,
    current_user: User = Depends(get_org_user)
):
    """Update a schema"""
    logger.info(f"update_schema() start: organization_id: {organization_id}, schema_id: {schema_id}, schema: {schema}")
    
    db = ad.common.get_async_db()

    # Check if user is a member of the organization
    org = await db.organizations.find_one({"_id": ObjectId(organization_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if user is a member of the organization
    if not any(member["user_id"] == current_user.user_id for member in org["members"]):
        raise HTTPException(status_code=403, detail="Not authorized to update schemas in this organization")

    # Get the existing schema and latest revision
    existing_schema = await db.schemas.find_one({"_id": ObjectId(schema_id)})
    if not existing_schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    latest_schema_revision = await db.schema_revisions.find_one(
        {"schema_id": schema_id},
        sort=[("schema_version", -1)]
    )
    
    if not latest_schema_revision:
        raise HTTPException(status_code=404, detail="Schema revision not found")

    # Check if only the name has changed
    only_name_changed = (
        schema.name != existing_schema["name"] and
        schema.response_format.model_dump() == latest_schema_revision["response_format"]
    )
    
    if only_name_changed:
        # Update the name in the schemas collection
        result = await db.schemas.update_one(
            {"_id": ObjectId(schema_id)},
            {"$set": {"name": schema.name}}
        )
        
        if result.modified_count > 0:
            # Return the updated schema
            updated_revision = latest_schema_revision.copy()
            updated_revision["schema_revid"] = str(updated_revision.pop("_id"))
            updated_revision["name"] = schema.name
            return Schema(**updated_revision)
        else:
            raise HTTPException(status_code=500, detail="Failed to update schema name")
    
    # If other fields changed, create a new version
    # Get the next version number using the stable schema_id
    _, new_schema_version = await get_schema_id_and_version(schema_id)
    
    # Update the schemas collection if name changed
    if schema.name != existing_schema["name"]:
        await db.schemas.update_one(
            {"_id": ObjectId(schema_id)},
            {"$set": {"name": schema.name}}
        )
    
    # Create new version of the schema in schema_revisions
    new_schema = {
        "schema_id": schema_id,
        "response_format": schema.response_format.model_dump(),
        "schema_version": new_schema_version,
        "created_at": datetime.now(UTC),
        "created_by": current_user.user_id
    }
    
    # Insert new version
    result = await db.schema_revisions.insert_one(new_schema)
    
    # Return updated schema
    new_schema["schema_revid"] = str(result.inserted_id)
    new_schema["name"] = schema.name
    return Schema(**new_schema)

@schemas_router.delete("/v0/orgs/{organization_id}/schemas/{schema_id}")
async def delete_schema(
    organization_id: str,
    schema_id: str,
    current_user: User = Depends(get_org_user)
):
    """Delete a schema"""
    logger.info(f"delete_schema() start: organization_id: {organization_id}, schema_id: {schema_id}")

    db = ad.common.get_async_db()
    
    # Get the schema and verify organization
    schema = await db.schemas.find_one({
        "_id": ObjectId(schema_id),
        "organization_id": organization_id
    })
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found or not in this organization")

    # Check for dependent prompts by schema_id
    dependent_prompts = await db.prompt_revisions.find({
        "schema_id": schema_id
    }).to_list(None)
    
    if dependent_prompts:
        # Get names from prompts collection
        prompt_names = {}
        for prompt_revision in dependent_prompts:
            prompt = await db.prompts.find_one({"_id": ObjectId(prompt_revision["prompt_id"])})
            if prompt:
                prompt_names[str(prompt_revision["_id"])] = prompt["name"]
        
        # Format the list of dependent prompts
        prompt_list = [
            {
                "name": prompt_names.get(str(p["_id"]), "Unknown"), 
                "schema_version": p["schema_version"]
            } 
            for p in dependent_prompts
        ]
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete schema because it has dependent prompts:{json.dumps(prompt_list)}"
        )
    
    # If no dependent prompts, proceed with deletion
    result = await db.schema_revisions.delete_many({
        "schema_id": schema_id
    })
    
    # Delete the schema entry
    await db.schemas.delete_one({"_id": ObjectId(schema_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No schema revisions found")
        
    return {"message": "Schema deleted successfully"}

@schemas_router.post("/v0/orgs/{organization_id}/schemas/{schema_revid}/validate")
async def validate_against_schema(
    organization_id: str,
    schema_revid: str,
    data: dict = Body(...),
    current_user: User = Depends(get_org_user)
):
    """Validate data against a schema revision"""
    logger.info(f"validate_against_schema() start: organization_id: {organization_id}, schema_revid: {schema_revid}")
    
    db = ad.common.get_async_db()
    
    # Get the schema
    schema_doc = await db.schema_revisions.find_one({
        "_id": ObjectId(schema_revid),
    })
    
    if not schema_doc:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    # Extract the JSON schema from the schema document
    try:
        json_schema = schema_doc["response_format"]["json_schema"]["schema"]
        
        # Get the data to validate
        if "data" not in data:
            raise HTTPException(status_code=400, detail="Request must include 'data' field")
        
        instance_data = data["data"]
        
        # Validate the data against the schema
        validator = Draft7Validator(json_schema)
        errors = list(validator.iter_errors(instance_data))
        
        if not errors:
            return {"valid": True}
        
        # Format validation errors
        formatted_errors = []
        for error in errors:
            formatted_errors.append({
                "path": ".".join(str(p) for p in error.path) if error.path else "",
                "message": error.message
            })
        
        return {
            "valid": False,
            "errors": formatted_errors
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")
