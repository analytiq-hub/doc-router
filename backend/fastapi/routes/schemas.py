from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, UTC
from bson import ObjectId

import analytiq_data as ad
from setup import get_async_db
from auth import get_current_user
from schemas import (
    Schema,
    SchemaCreate,
    ListSchemasResponse,
    User
)

schemas_router = APIRouter(
    prefix="/schemas",
    tags=["schemas"]
)

async def get_next_schema_version(schema_name: str) -> int:
    """Atomically get the next version number for a schema"""
    db = get_async_db()
    result = await db.schema_versions.find_one_and_update(
        {"_id": schema_name},
        {"$inc": {"version": 1}},
        upsert=True,
        return_document=True
    )
    return result["version"]

def validate_schema_fields(fields: list) -> tuple[bool, str]:
    field_names = [field.name.lower() for field in fields]
    seen = set()
    for name in field_names:
        if name in seen:
            return False, f"Duplicate field name: {name}"
        seen.add(name)
    return True, ""

@schemas_router.post("", response_model=Schema)
async def create_schema(
    schema: SchemaCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a schema"""
    db = get_async_db()
    
    # Check if schema with this name already exists (case-insensitive)
    existing_schema = await db.schemas.find_one({
        "name": {"$regex": f"^{schema.name}$", "$options": "i"}
    })
    
    # If schema exists, treat this as an update operation
    if existing_schema:
        # Get the next version
        new_version = await get_next_schema_version(schema.name)
        
        # Create new version of the schema
        schema_dict = {
            "name": existing_schema["name"],  # Use existing name to preserve case
            "fields": [field.model_dump() for field in schema.fields],
            "version": new_version,
            "created_at": datetime.utcnow(),
            "created_by": current_user.user_id
        }
    else:
        # This is a new schema
        new_version = await get_next_schema_version(schema.name)
        schema_dict = {
            "name": schema.name,
            "fields": [field.model_dump() for field in schema.fields],
            "version": new_version,
            "created_at": datetime.utcnow(),
            "created_by": current_user.user_id
        }
    
    # Insert into MongoDB
    result = await db.schemas.insert_one(schema_dict)
    
    # Return complete schema
    schema_dict["id"] = str(result.inserted_id)
    return Schema(**schema_dict)

@schemas_router.get("", response_model=ListSchemasResponse)
async def list_schemas(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """List schemas"""
    db = get_async_db()
    
    # Build the base pipeline
    pipeline = [
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
                "schemas": [
                    {"$skip": skip},
                    {"$limit": limit}
                ]
            }
        }
    ]
    
    result = await db.schemas.aggregate(pipeline).to_list(length=1)
    result = result[0]
    
    total_count = result["total"][0]["count"] if result["total"] else 0
    schemas = result["schemas"]
    
    # Convert _id to id in each schema
    for schema in schemas:
        schema['id'] = str(schema.pop('_id'))
    
    return ListSchemasResponse(
        schemas=schemas,
        total_count=total_count,
        skip=skip
    )

@schemas_router.get("/{schema_id}", response_model=Schema)
async def get_schema(
    schema_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a schema"""
    db = get_async_db()
    
    schema = await db.schemas.find_one({"_id": ObjectId(schema_id)})
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    schema['id'] = str(schema.pop('_id'))
    return Schema(**schema)

@schemas_router.put("/{schema_id}", response_model=Schema)
async def update_schema(
    schema_id: str,
    schema: SchemaCreate,
    current_user: User = Depends(get_current_user)
):
    """Update a schema"""
    db = get_async_db()
    
    # Get the existing schema
    existing_schema = await db.schemas.find_one({"_id": ObjectId(schema_id)})
    if not existing_schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    # Check if user has permission to update
    if existing_schema["created_by"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this schema")
    
    # Validate field names
    is_valid, error_msg = validate_schema_fields(schema.fields)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=error_msg
        )
    
    # Atomically get the next version number
    new_version = await get_next_schema_version(existing_schema["name"])
    
    # Create new version of the schema
    new_schema = {
        "name": schema.name,
        "fields": [field.model_dump() for field in schema.fields],
        "version": new_version,
        "created_at": datetime.utcnow(),
        "created_by": current_user.user_id
    }
    
    # Insert new version
    result = await db.schemas.insert_one(new_schema)
    
    # Return updated schema
    new_schema["id"] = str(result.inserted_id)
    return Schema(**new_schema)

@schemas_router.delete("/{schema_id}")
async def delete_schema(
    schema_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a schema"""
    db = get_async_db()
    
    # Get the schema to find its name
    schema = await db.schemas.find_one({"_id": ObjectId(schema_id)})
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    if schema["created_by"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this schema")
    
    # Check for dependent prompts
    dependent_prompts = await db.prompts.find({
        "schema_name": schema["name"]
    }).to_list(length=None)
    
    if dependent_prompts:
        # Format the list of dependent prompts
        prompt_list = [
            {"name": p["name"], "version": p["version"]} 
            for p in dependent_prompts
        ]
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete schema because it has dependent prompts:{json.dumps(prompt_list)}"
        )
    
    # If no dependent prompts, proceed with deletion
    result = await db.schemas.delete_many({"name": schema["name"]})
    
    # Also delete the version counter
    await db.schema_versions.delete_one({"_id": schema["name"]})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {"message": "Schema deleted successfully"} 