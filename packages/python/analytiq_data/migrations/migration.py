from datetime import datetime, UTC
import os
import logging

import analytiq_data as ad

logger = logging.getLogger(__name__)

class Migration:
    def __init__(self, description: str):
        self.description = description
        # Version will be set when migrations are loaded
        self.version = None
        
    async def up(self, db) -> bool:
        """Execute the migration"""
        raise NotImplementedError
        
    async def down(self, db) -> bool:
        """Revert the migration"""
        raise NotImplementedError

async def get_current_version(db) -> int:
    """Get the current schema version"""
    migration_doc = await db.migrations.find_one(
        {"_id": "schema_version"},
        sort=[("version", -1)]
    )
    return migration_doc["version"] if migration_doc else 0

async def run_migrations(analytiq_client, target_version: int = None) -> None:
    """Run all pending migrations or up to target_version"""
    db = analytiq_client.mongodb_async[analytiq_client.env]
    current_version = await get_current_version(db)
    
    if target_version is None:
        target_version = len(MIGRATIONS)
        
    logger.info(f"Db current version: {current_version}, target version: {target_version}")

    try:
        if target_version > current_version:
            # Run migrations up
            for migration in MIGRATIONS[current_version:target_version]:
                logger.info(f"Running migration {migration.version}: {migration.description}")
                success = await migration.up(db)
                if success:
                    await db.migrations.update_one(
                        {"_id": "schema_version"},
                        {
                            "$set": {
                                "version": migration.version,
                                "updated_at": datetime.now(UTC)
                            }
                        },
                        upsert=True
                    )
                else:
                    raise Exception(f"Migration {migration.version} failed")
                    
        elif target_version < current_version:
            # Run migrations down
            for migration in reversed(MIGRATIONS[target_version:current_version]):
                logger.info(f"Reverting migration {migration.version}")
                success = await migration.down(db)
                if success:
                    await db.migrations.update_one(
                        {"_id": "schema_version"},
                        {
                            "$set": {
                                "version": migration.version - 1,
                                "updated_at": datetime.now(UTC)
                            }
                        }
                    )
                else:
                    raise Exception(f"Migration revert {migration.version} failed")
                    
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

# Example migration for OCR key renaming
class OcrKeyMigration(Migration):
    def __init__(self):
        super().__init__(description="Rename OCR keys from _list to _json")
        
    async def up(self, db) -> bool:
        try:
            cursor = db["ocr.files"].find({"filename": {"$regex": "_list$"}})
            async for doc in cursor:
                old_key = doc["filename"]
                new_key = old_key.replace("_list", "_json")
                await db["ocr.files"].update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"filename": new_key}}
                )
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
            
    async def down(self, db) -> bool:
        try:
            cursor = db["ocr.files"].find({"filename": {"$regex": "_json$"}})
            async for doc in cursor:
                old_key = doc["filename"]
                new_key = old_key.replace("_json", "_list")
                await db["ocr.files"].update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"filename": new_key}}
                )
            return True
        except Exception as e:
            logger.error(f"Migration revert failed: {e}")
            return False

class LlmResultFieldsMigration(Migration):
    def __init__(self):
        super().__init__(description="Add new fields to LLM results")
        
    async def up(self, db) -> bool:
        """Add updated_llm_result, is_edited, is_verified, created_at, updated_at fields"""
        try:
            current_time = datetime.now(UTC)
            
            # Find all documents in llm.runs collection
            cursor = db["llm.runs"].find({})
            async for doc in cursor:
                update_fields = {}
                
                # Add updated_llm_result if missing
                if "updated_llm_result" not in doc:
                    update_fields["updated_llm_result"] = doc["llm_result"]
                
                # Add timestamps if missing
                if "created_at" not in doc:
                    update_fields["created_at"] = current_time
                if "updated_at" not in doc:
                    update_fields["updated_at"] = current_time
                    
                # Add status flags if missing
                if "is_edited" not in doc:
                    update_fields["is_edited"] = False
                if "is_verified" not in doc:
                    update_fields["is_verified"] = False
                
                # Only update if there are missing fields
                if update_fields:
                    await db["llm.runs"].update_one(
                        {"_id": doc["_id"]},
                        {"$set": update_fields}
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"LLM results migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """Remove added fields"""
        try:
            await db["llm.runs"].update_many(
                {},
                {
                    "$unset": {
                        "updated_llm_result": "",
                        "is_edited": "",
                        "is_verified": "",
                        "created_at": "",
                        "updated_at": ""
                    }
                }
            )
            return True
            
        except Exception as e:
            logger.error(f"LLM results migration revert failed: {e}")
            return False

# Add this new migration class
class SchemaJsonSchemaMigration(Migration):
    def __init__(self):
        super().__init__(description="Convert schemas to JsonSchema format")
        
    def convert_to_json_schema(self, fields):
        """Convert old field format to JsonSchema format"""
        json_schema = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        }
        
        for field in fields:
            field_name = field["name"]
            field_type = field["type"]
            
            # Convert Python/Pydantic types to JSON Schema types
            if field_type == "str":
                json_type = "string"
            elif field_type == "int":
                json_type = "integer"
            elif field_type == "float":
                json_type = "number"
            elif field_type == "bool":
                json_type = "boolean"
            else:
                json_type = "string"
            
            json_schema["properties"][field_name] = {
                "type": json_type,
                "description": field_name.replace("_", " ")
            }
            json_schema["required"].append(field_name)
        
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "document_extraction",
                "schema": json_schema,
                "strict": True
            }
        }
        
    async def up(self, db) -> bool:
        """Convert existing schemas to JsonSchema format"""
        try:
            cursor = db.schemas.find({})
            async for schema in cursor:
                # Convert fields to JsonSchema
                json_schema = self.convert_to_json_schema(schema["fields"])
                
                # Update the document
                await db.schemas.update_one(
                    {"_id": schema["_id"]},
                    {
                        "$set": {
                            "json_schema": json_schema,
                            "schema_format": "json_schema"
                        },
                        "$unset": {"fields": ""}
                    }
                )
            return True
            
        except Exception as e:
            logger.error(f"Schema migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """Convert JsonSchema back to old format"""
        try:
            cursor = db.schemas.find({"schema_format": "json_schema"})
            async for schema in cursor:
                json_schema = schema.get("json_schema", {})
                properties = json_schema.get("json_schema", {}).get("schema", {}).get("properties", {})
                
                fields = []
                for field_name, field_def in properties.items():
                    field_type = field_def["type"]
                    if field_type == "string":
                        field_type = "str"
                    elif field_type == "integer":
                        field_type = "int"
                    elif field_type == "number":
                        field_type = "float"
                    elif field_type == "boolean":
                        field_type = "bool"
                    
                    fields.append({
                        "name": field_name,
                        "type": field_type
                    })
                
                await db.schemas.update_one(
                    {"_id": schema["_id"]},
                    {
                        "$set": {"fields": fields},
                        "$unset": {
                            "json_schema": "",
                            "schema_format": ""
                        }
                    }
                )
            return True
            
        except Exception as e:
            logger.error(f"Schema migration revert failed: {e}")
            return False

class RenameJsonSchemaToResponseFormat(Migration):
    def __init__(self):
        super().__init__(description="Rename json_schema field to response_format in schemas collection")

    async def up(self, db) -> bool:
        try:
            # Update all documents in schemas collection
            result = await db.schemas.update_many(
                {"json_schema": {"$exists": True}},
                [
                    {
                        "$set": {
                            "response_format": "$json_schema",
                            "json_schema": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Updated {result.modified_count} schemas")
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    async def down(self, db) -> bool:
        try:
            # Revert the changes
            result = await db.schemas.update_many(
                {"response_format": {"$exists": True}},
                [
                    {
                        "$set": {
                            "json_schema": "$response_format",
                            "response_format": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Reverted {result.modified_count} schemas")
            return True
        except Exception as e:
            logger.error(f"Migration revert failed: {e}")
            return False

class RemoveSchemaFormatField(Migration):
    def __init__(self):
        super().__init__(description="Remove redundant schema_format field from schemas collection")

    async def up(self, db) -> bool:
        try:
            result = await db.schemas.update_many(
                {"schema_format": {"$exists": True}},
                {"$unset": {"schema_format": ""}}
            )
            logger.info(f"Removed schema_format field from {result.modified_count} schemas")
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    async def down(self, db) -> bool:
        try:
            # Restore schema_format field to 'json_schema' for all documents
            result = await db.schemas.update_many(
                {},
                {"$set": {"schema_format": "json_schema"}}
            )
            logger.info(f"Restored schema_format field to {result.modified_count} schemas")
            return True
        except Exception as e:
            logger.error(f"Migration revert failed: {e}")
            return False

# Add this new migration class
class AddStableIdentifiers(Migration):
    def __init__(self):
        super().__init__(description="Add stable schema_id and prompt_id fields to schemas and prompts")
        
    async def up(self, db) -> bool:
        """Add schema_id and prompt_id fields"""
        try:
            # First, get existing normalized IDs to avoid duplicates
            existing_schema_ids = set()
            existing_prompt_ids = set()
            
            async for doc in db.schema_versions.find({}):
                existing_schema_ids.add(doc["_id"])
                
            async for doc in db.prompt_versions.find({}):
                existing_prompt_ids.add(doc["_id"])
            
            # Process schema_versions collection
            schema_versions_cursor = db.schema_versions.find({})
            to_delete_schema_ids = []
            to_insert_schema_docs = []
            schema_id_map = {}  # original_id -> normalized_id
            
            async for version_doc in schema_versions_cursor:
                original_id = version_doc["_id"]
                base_id = original_id.lower().replace(" ", "_")
                
                # Ensure ID uniqueness
                normalized_id = base_id
                counter = 1
                while normalized_id in existing_schema_ids and normalized_id != original_id:
                    normalized_id = f"{base_id}_{counter}"
                    counter += 1
                
                existing_schema_ids.add(normalized_id)
                schema_id_map[original_id] = normalized_id
                
                if normalized_id != original_id:
                    to_delete_schema_ids.append(original_id)
                    to_insert_schema_docs.append({
                        "_id": normalized_id,
                        "version": version_doc["version"]
                    })
            
            # Process prompt_versions collection
            prompt_versions_cursor = db.prompt_versions.find({})
            to_delete_prompt_ids = []
            to_insert_prompt_docs = []
            prompt_id_map = {}  # original_id -> normalized_id
            
            async for version_doc in prompt_versions_cursor:
                original_id = version_doc["_id"]
                base_id = original_id.lower().replace(" ", "_")
                
                # Ensure ID uniqueness
                normalized_id = base_id
                counter = 1
                while normalized_id in existing_prompt_ids and normalized_id != original_id:
                    normalized_id = f"{base_id}_{counter}"
                    counter += 1
                
                existing_prompt_ids.add(normalized_id)
                prompt_id_map[original_id] = normalized_id
                
                if normalized_id != original_id:
                    to_delete_prompt_ids.append(original_id)
                    to_insert_prompt_docs.append({
                        "_id": normalized_id,
                        "version": version_doc["version"]
                    })
            
            # Insert new documents first (to avoid conflicts if IDs already normalized)
            for doc in to_insert_schema_docs:
                try:
                    await db.schema_versions.insert_one(doc)
                except Exception as e:
                    logger.warning(f"Could not insert schema version {doc['_id']}: {e}")
            
            for doc in to_insert_prompt_docs:
                try:
                    await db.prompt_versions.insert_one(doc)
                except Exception as e:
                    logger.warning(f"Could not insert prompt version {doc['_id']}: {e}")
            
            # Then delete old documents
            for old_id in to_delete_schema_ids:
                try:
                    await db.schema_versions.delete_one({"_id": old_id})
                except Exception as e:
                    logger.warning(f"Could not delete schema version {old_id}: {e}")
            
            for old_id in to_delete_prompt_ids:
                try:
                    await db.prompt_versions.delete_one({"_id": old_id})
                except Exception as e:
                    logger.warning(f"Could not delete prompt version {old_id}: {e}")
            
            # Add schema_id to schemas
            schemas_cursor = db.schemas.find({"schema_id": {"$exists": False}})
            schema_names_processed = set()
            
            async for schema in schemas_cursor:
                schema_name = schema["name"]
                
                if schema_name not in schema_names_processed:
                    # Get normalized ID from map or create if not exists
                    if schema_name in schema_id_map:
                        schema_id = schema_id_map[schema_name]
                    else:
                        base_id = schema_name.lower().replace(" ", "_")
                        schema_id = base_id
                        counter = 1
                        while schema_id in existing_schema_ids and schema_id != schema_name:
                            schema_id = f"{base_id}_{counter}"
                            counter += 1
                    
                    schema_names_processed.add(schema_name)
                    
                    # Update all versions of this schema with the same schema_id
                    await db.schemas.update_many(
                        {"name": schema_name},
                        {"$set": {"schema_id": schema_id}}
                    )
            
            # Add prompt_id to prompts
            prompts_cursor = db.prompts.find({"prompt_id": {"$exists": False}})
            prompt_names_processed = set()
            
            async for prompt in prompts_cursor:
                prompt_name = prompt["name"]
                
                if prompt_name not in prompt_names_processed:
                    # Get normalized ID from map or create if not exists
                    if prompt_name in prompt_id_map:
                        prompt_id = prompt_id_map[prompt_name]
                    else:
                        base_id = prompt_name.lower().replace(" ", "_")
                        prompt_id = base_id
                        counter = 1
                        while prompt_id in existing_prompt_ids and prompt_id != prompt_name:
                            prompt_id = f"{base_id}_{counter}"
                            counter += 1
                    
                    prompt_names_processed.add(prompt_name)
                    
                    # Update all versions with prompt_id
                    update_doc = {"prompt_id": prompt_id}
                    
                    # Also update schema_id if schema_name exists
                    if "schema_name" in prompt and prompt["schema_name"]:
                        if prompt["schema_name"] in schema_id_map:
                            update_doc["schema_id"] = schema_id_map[prompt["schema_name"]]
                        else:
                            schema_id = prompt["schema_name"].lower().replace(" ", "_")
                            update_doc["schema_id"] = schema_id
                    
                    await db.prompts.update_many(
                        {"name": prompt_name},
                        {"$set": update_doc}
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """Remove schema_id and prompt_id fields"""
        try:
            # Get mappings of ids to names
            schema_id_to_name = {}
            prompt_id_to_name = {}
            
            async for schema in db.schemas.find({"schema_id": {"$exists": True}}):
                schema_id_to_name[schema["schema_id"]] = schema["name"]
            
            async for prompt in db.prompts.find({"prompt_id": {"$exists": True}}):
                prompt_id_to_name[prompt["prompt_id"]] = prompt["name"]
            
            # Collect version entries to restore
            schema_versions_to_restore = []
            existing_schema_versions = set()
            
            async for version_doc in db.schema_versions.find({}):
                schema_id = version_doc["_id"]
                if schema_id in schema_id_to_name:
                    schema_name = schema_id_to_name[schema_id]
                    if schema_name not in existing_schema_versions:
                        schema_versions_to_restore.append({
                            "_id": schema_name,
                            "version": version_doc["version"]
                        })
                        existing_schema_versions.add(schema_name)
            
            prompt_versions_to_restore = []
            existing_prompt_versions = set()
            
            async for version_doc in db.prompt_versions.find({}):
                prompt_id = version_doc["_id"]
                if prompt_id in prompt_id_to_name:
                    prompt_name = prompt_id_to_name[prompt_id]
                    if prompt_name not in existing_prompt_versions:
                        prompt_versions_to_restore.append({
                            "_id": prompt_name,
                            "version": version_doc["version"]
                        })
                        existing_prompt_versions.add(prompt_name)
            
            # Insert new documents before removing old ones
            for doc in schema_versions_to_restore:
                try:
                    await db.schema_versions.insert_one(doc)
                except Exception as e:
                    logger.warning(f"Could not insert schema version with original name {doc['_id']}: {e}")
            
            for doc in prompt_versions_to_restore:
                try:
                    await db.prompt_versions.insert_one(doc)
                except Exception as e:
                    logger.warning(f"Could not insert prompt version with original name {doc['_id']}: {e}")
            
            # Remove new normalized version entries 
            for schema_id in schema_id_to_name.keys():
                try:
                    await db.schema_versions.delete_one({"_id": schema_id})
                except Exception as e:
                    logger.warning(f"Could not delete schema version {schema_id}: {e}")
            
            for prompt_id in prompt_id_to_name.keys():
                try:
                    await db.prompt_versions.delete_one({"_id": prompt_id})
                except Exception as e:
                    logger.warning(f"Could not delete prompt version {prompt_id}: {e}")
            
            # Remove fields from schemas and prompts
            await db.schemas.update_many(
                {"schema_id": {"$exists": True}},
                {"$unset": {"schema_id": ""}}
            )
            
            await db.prompts.update_many(
                {
                    "$or": [
                        {"prompt_id": {"$exists": True}},
                        {"schema_id": {"$exists": True}}
                    ]
                },
                {
                    "$unset": {
                        "prompt_id": "",
                        "schema_id": ""
                    }
                }
            )
            
            return True
        except Exception as e:
            logger.error(f"Migration revert failed: {e}")
            return False

# Add migration to rename the 'version' field to 'prompt_version' in prompts collection
class RenamePromptVersion(Migration):
    def __init__(self):
        super().__init__(description="Rename version field to prompt_version in prompts collection")

    async def up(self, db) -> bool:
        try:
            # Update all documents in prompts collection
            result = await db.prompts.update_many(
                {},
                [
                    {
                        "$set": {
                            "prompt_version": "$version",
                            "version": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Updated {result.modified_count} prompts")
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    async def down(self, db) -> bool:
        try:
            # Revert the changes
            result = await db.prompts.update_many(
                {},
                [
                    {
                        "$set": {
                            "version": "$prompt_version",
                            "prompt_version": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Reverted {result.modified_count} prompts")
            return True
        except Exception as e:
            logger.error(f"Migration revert failed: {e}")
            return False

# Add a migration to rename 'version' to 'schema_version' in schemas collection
class RenameSchemaVersion(Migration):
    def __init__(self):
        super().__init__(description="Rename version to schema_version in schemas collection")
    
    async def up(self, db) -> bool:
        try:
            # Update all documents in schemas collection
            async for schema in db.schemas.find({}):
                await db.schemas.update_one(
                    {"_id": schema["_id"]},
                    {"$rename": {"version": "schema_version"}}
                )
            
            # Update all documents in schema_versions collection
            async for doc in db.schema_versions.find({}):
                await db.schema_versions.update_one(
                    {"_id": doc["_id"]},
                    {"$rename": {"version": "schema_version"}}
                )
            
            return True
        except Exception as e:
            logger.error(f"Schema version rename migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        try:
            # Revert changes
            async for schema in db.schemas.find({}):
                await db.schemas.update_one(
                    {"_id": schema["_id"]},
                    {"$rename": {"schema_version": "version"}}
                )
            
            async for doc in db.schema_versions.find({}):
                await db.schema_versions.update_one(
                    {"_id": doc["_id"]},
                    {"$rename": {"schema_version": "version"}}
                )
            
            return True
        except Exception as e:
            logger.error(f"Schema version rename migration revert failed: {e}")
            return False

# Add this new migration class before the MIGRATIONS list
class RemoveSchemaNameField(Migration):
    def __init__(self):
        super().__init__(description="Remove schema_name field from prompts collection")
        
    async def up(self, db) -> bool:
        """Remove schema_name field from prompts collection"""
        try:
            # Remove schema_name field from all documents in prompts collection
            result = await db.prompts.update_many(
                {"schema_name": {"$exists": True}},
                {"$unset": {"schema_name": ""}}
            )
            
            logger.info(f"Removed schema_name field from {result.modified_count} documents")
            return True
            
        except Exception as e:
            logger.error(f"Remove schema_name field migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """Restore schema_name field using schema_id to look up schemas"""
        try:
            # For each prompt with schema_id, look up the schema and add its name
            cursor = db.prompts.find({"schema_id": {"$exists": True, "$ne": None}})
            
            restored_count = 0
            async for prompt in cursor:
                if "schema_id" in prompt and prompt["schema_id"]:
                    # Find the corresponding schema
                    schema = await db.schemas.find_one({
                        "schema_id": prompt["schema_id"],
                        "schema_version": prompt.get("schema_version", 1)
                    })
                    
                    if schema and "name" in schema:
                        # Update the prompt with the schema name
                        await db.prompts.update_one(
                            {"_id": prompt["_id"]},
                            {"$set": {"schema_name": schema["name"]}}
                        )
                        restored_count += 1
            
            logger.info(f"Restored schema_name field for {restored_count} documents")
            return True
            
        except Exception as e:
            logger.error(f"Restore schema_name field migration failed: {e}")
            return False

# Add this new migration class before the MIGRATIONS list
class RenameCollections(Migration):
    def __init__(self):
        super().__init__(description="Rename schema and prompt collections to match new architecture")
        
    async def up(self, db) -> bool:
        """Rename collections: 
           schemas → schema_revisions
           schema_versions → schemas
           prompts → prompt_revisions
           prompt_versions → prompts
        """
        try:
            # Create new collections with data from old ones
            # 1. Copy schemas to schema_revisions
            schemas_cursor = db.schemas.find({})
            async for doc in schemas_cursor:
                await db.schema_revisions.insert_one(doc)
            
            # 2. Drop the schemas collection
            await db.schemas.drop()
            
            # 3. Copy schema_versions to schemas
            schema_versions_cursor = db.schema_versions.find({})
            async for doc in schema_versions_cursor:
                await db.schemas.insert_one(doc)
            
            # 4. Drop the schema_versions collection
            await db.schema_versions.drop()
            
            # 5. Copy prompts to prompt_revisions
            prompts_cursor = db.prompts.find({})
            async for doc in prompts_cursor:
                await db.prompt_revisions.insert_one(doc)
            
            # 6. Drop the prompts collection
            await db.prompts.drop()
            
            # 7. Copy prompt_versions to prompts
            prompt_versions_cursor = db.prompt_versions.find({})
            async for doc in prompt_versions_cursor:
                await db.prompts.insert_one(doc)
            
            # 8. Drop the prompt_versions collection
            await db.prompt_versions.drop()

            # 9. In the prompts collection, rename the version field to prompt_version
            await db.prompts.update_many(
                {},
                {"$rename": {"version": "prompt_version"}}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Collection rename migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """Revert collection renaming:
           schema_revisions → schemas
           schemas → schema_versions
           prompt_revisions → prompts
           prompts → prompt_versions
        """
        try:
            # Create old collections with data from new ones
            # 1. Copy schema_revisions to schemas
            schema_revisions_cursor = db.schema_revisions.find({})
            async for doc in schema_revisions_cursor:
                await db.schemas.insert_one(doc)
            
            # 2. Copy schemas to schema_versions
            schemas_cursor = db.schemas.find({})
            async for doc in schemas_cursor:
                await db.schema_versions.insert_one(doc)
            
            # 3. Copy prompt_revisions to prompts
            prompt_revisions_cursor = db.prompt_revisions.find({})
            async for doc in prompt_revisions_cursor:
                await db.prompts.insert_one(doc)
            
            # 4. Copy prompts to prompt_versions
            prompts_cursor = db.prompts.find({})
            async for doc in prompts_cursor:
                await db.prompt_versions.insert_one(doc)
            
            # Drop new collections (in reverse order to avoid conflicts)
            await db.prompts.drop()
            await db.prompt_revisions.drop()
            await db.schemas.drop()
            await db.schema_revisions.drop()
            
            return True
            
        except Exception as e:
            logger.error(f"Collection rename migration revert failed: {e}")
            return False

# Add this new migration class before the MIGRATIONS list
class UseMongoObjectIDs(Migration):
    def __init__(self):
        super().__init__(description="Convert schema and prompt IDs to MongoDB ObjectIDs")
        
    async def up(self, db) -> bool:
        """
        Convert schema and prompt IDs to MongoDB ObjectIDs and update references in revisions.
        """
        try:
            from bson import ObjectId
            
            # Process schemas first
            schema_mapping = {}  # old_id -> new_objectid
            
            # Get all existing schemas
            schemas_cursor = db.schemas.find({})
            schema_docs = []
            async for schema in schemas_cursor:
                schema_docs.append(schema)
            
            # For each schema, create a new document with ObjectId
            for old_schema in schema_docs:
                old_id = old_schema["_id"]
                
                # Create a new document with a new ObjectId
                new_schema = old_schema.copy()
                del new_schema["_id"]  # Remove _id to let MongoDB generate a new one
                
                result = await db.schemas.insert_one(new_schema)
                new_id = result.inserted_id
                
                # Store mapping
                schema_mapping[old_id] = new_id
                
                # Delete old document
                await db.schemas.delete_one({"_id": old_id})
                
                logger.info(f"Converted schema ID: {old_id} -> {new_id}")
            
            # Update schema_revisions to reference new schema IDs
            revisions_cursor = db.schema_revisions.find({"schema_id": {"$exists": True}})
            async for revision in revisions_cursor:
                old_id = revision.get("schema_id")
                if old_id in schema_mapping:
                    new_id = schema_mapping[old_id]
                    await db.schema_revisions.update_one(
                        {"_id": revision["_id"]},
                        {"$set": {"schema_id": str(new_id)}}
                    )
            
            # Process prompts
            prompt_mapping = {}  # old_id -> new_objectid
            
            # Get all existing prompts
            prompts_cursor = db.prompts.find({})
            prompt_docs = []
            async for prompt in prompts_cursor:
                prompt_docs.append(prompt)
            
            # For each prompt, create a new document with ObjectId
            for old_prompt in prompt_docs:
                old_id = old_prompt["_id"]
                
                # Create a new document with a new ObjectId
                new_prompt = old_prompt.copy()
                del new_prompt["_id"]  # Remove _id to let MongoDB generate a new one
                
                # Update schema_id reference if it exists
                if "schema_id" in new_prompt and new_prompt["schema_id"] in schema_mapping:
                    new_prompt["schema_id"] = str(schema_mapping[new_prompt["schema_id"]])
                
                result = await db.prompts.insert_one(new_prompt)
                new_id = result.inserted_id
                
                # Store mapping
                prompt_mapping[old_id] = new_id
                
                # Delete old document
                await db.prompts.delete_one({"_id": old_id})
                
                logger.info(f"Converted prompt ID: {old_id} -> {new_id}")
            
            # Update prompt_revisions to reference new prompt IDs
            revisions_cursor = db.prompt_revisions.find({"prompt_id": {"$exists": True}})
            async for revision in revisions_cursor:
                old_id = revision.get("prompt_id")
                if old_id in prompt_mapping:
                    new_id = prompt_mapping[old_id]
                    await db.prompt_revisions.update_one(
                        {"_id": revision["_id"]},
                        {"$set": {"prompt_id": str(new_id)}}
                    )
                
                # Also update schema_id if it exists
                if "schema_id" in revision and revision["schema_id"] in schema_mapping:
                    new_schema_id = schema_mapping[revision["schema_id"]]
                    await db.prompt_revisions.update_one(
                        {"_id": revision["_id"]},
                        {"$set": {"schema_id": str(new_schema_id)}}
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"Migration to MongoDB ObjectIDs failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """
        It's not practical to revert this migration as the original IDs are lost.
        This is a one-way migration.
        """
        logger.warning("Cannot revert migration to MongoDB ObjectIDs as original IDs are not preserved.")
        return False

# Add this new migration class before the MIGRATIONS list
class MigratePromptNames(Migration):
    def __init__(self):
        super().__init__(description="Copy prompt names from prompt_revisions to prompts")
        
    async def up(self, db) -> bool:
        """Copy prompt names from prompt_revisions to prompts, then delete the names from prompt_revisions"""
        try:
            # Get all prompts
            prompts_cursor = db.prompts.find({})
            
            updated_count = 0
            skipped_count = 0
            
            async for prompt in prompts_cursor:
                prompt_id = prompt.get("_id")
                prompt_version = prompt.get("prompt_version", 1)
                
                # Skip if prompt already has a name
                if "name" in prompt and prompt["name"]:
                    skipped_count += 1
                    continue
                
                # Find corresponding prompt_revision
                revision = await db.prompt_revisions.find_one({
                    "prompt_id": str(prompt_id),
                    "prompt_version": prompt_version
                })
                
                if revision and "name" in revision:
                    # Copy name to the prompt
                    await db.prompts.update_one(
                        {"_id": prompt_id},
                        {"$set": {"name": revision["name"]}}
                    )
                    updated_count += 1
            
            logger.info(f"Updated {updated_count} prompts with names, skipped {skipped_count} prompts")
            
            # Remove name field from all prompt_revisions
            result = await db.prompt_revisions.update_many(
                {"name": {"$exists": True}},
                {"$unset": {"name": ""}}
            )
            
            logger.info(f"Removed name field from {result.modified_count} prompt_revisions")
            
            return True
            
        except Exception as e:
            logger.error(f"Prompt name migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """Restore prompt names from prompts to prompt_revisions"""
        try:
            # For each prompt, copy its name back to all matching prompt_revisions
            prompts_cursor = db.prompts.find({"name": {"$exists": True}})
            
            restored_count = 0
            async for prompt in prompts_cursor:
                prompt_id = prompt.get("_id")
                name = prompt.get("name")
                
                if name:
                    # Find all revisions for this prompt
                    result = await db.prompt_revisions.update_many(
                        {"prompt_id": str(prompt_id)},
                        {"$set": {"name": name}}
                    )
                    
                    restored_count += result.modified_count
            
            logger.info(f"Restored name field for {restored_count} prompt_revisions")
            return True
            
        except Exception as e:
            logger.error(f"Prompt name migration revert failed: {e}")
            return False

# Add this new migration class before the MIGRATIONS list
class MigratePromptOrganizationIDs(Migration):
    def __init__(self):
        super().__init__(description="Copy organization_id from prompt_revisions to prompts")
        
    async def up(self, db) -> bool:
        """Copy organization_id from prompt_revisions to prompts, then delete them from prompt_revisions"""
        try:
            # Get all prompts
            prompts_cursor = db.prompts.find({})
            
            updated_count = 0
            
            async for prompt in prompts_cursor:
                prompt_id = prompt.get("_id")
                prompt_version = prompt.get("prompt_version", 1)
                
                # Find corresponding prompt_revision
                revision = await db.prompt_revisions.find_one({
                    "prompt_id": str(prompt_id),
                    "prompt_version": prompt_version
                })
                
                if revision:
                    update_fields = {}
                    
                    # Copy name if not already present in prompt
                    if "name" not in prompt and "name" in revision:
                        update_fields["name"] = revision["name"]
                    
                    # Copy organization_id
                    if "organization_id" in revision:
                        update_fields["organization_id"] = revision["organization_id"]
                    
                    if update_fields:
                        await db.prompts.update_one(
                            {"_id": prompt_id},
                            {"$set": update_fields}
                        )
                        updated_count += 1
            
            logger.info(f"Updated {updated_count} prompts with organization_id/name")
            
            # Remove fields from all prompt_revisions
            result = await db.prompt_revisions.update_many(
                {"$or": [
                    {"name": {"$exists": True}},
                    {"organization_id": {"$exists": True}}
                ]},
                {"$unset": {
                    "name": "",
                    "organization_id": ""
                }}
            )
            
            logger.info(f"Removed fields from {result.modified_count} prompt_revisions")
            
            return True
            
        except Exception as e:
            logger.error(f"Organization ID migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """Restore organization_id and name from prompts to prompt_revisions"""
        try:
            # For each prompt, copy its organization_id back to all matching prompt_revisions
            prompts_cursor = db.prompts.find({
                "$or": [
                    {"name": {"$exists": True}},
                    {"organization_id": {"$exists": True}}
                ]
            })
            
            restored_count = 0
            async for prompt in prompts_cursor:
                prompt_id = prompt.get("_id")
                update_fields = {}
                
                if "name" in prompt:
                    update_fields["name"] = prompt["name"]
                
                if "organization_id" in prompt:
                    update_fields["organization_id"] = prompt["organization_id"]
                
                if update_fields:
                    # Find all revisions for this prompt
                    result = await db.prompt_revisions.update_many(
                        {"prompt_id": str(prompt_id)},
                        {"$set": update_fields}
                    )
                    
                    restored_count += result.modified_count
            
            logger.info(f"Restored fields for {restored_count} prompt_revisions")
            return True
            
        except Exception as e:
            logger.error(f"Organization ID migration revert failed: {e}")
            return False

# Add this new migration class before the MIGRATIONS list
class MigrateSchemaOrganizationIDs(Migration):
    def __init__(self):
        super().__init__(description="Copy organization_id from schema_revisions to schemas")
        
    async def up(self, db) -> bool:
        """Copy organization_id from schema_revisions to schemas, then delete them from schema_revisions"""
        try:
            # Get all schemas
            schemas_cursor = db.schemas.find({})
            
            updated_count = 0
            
            async for schema in schemas_cursor:
                schema_id = schema.get("_id")
                schema_version = schema.get("schema_version", 1)
                
                # Find corresponding schema_revision
                revision = await db.schema_revisions.find_one({
                    "schema_id": str(schema_id),
                    "schema_version": schema_version
                })
                
                if revision:
                    update_fields = {}
                    
                    # Copy name if not already present in schema
                    if "name" not in schema and "name" in revision:
                        update_fields["name"] = revision["name"]
                    
                    # Copy organization_id
                    if "organization_id" in revision:
                        update_fields["organization_id"] = revision["organization_id"]
                    
                    if update_fields:
                        await db.schemas.update_one(
                            {"_id": schema_id},
                            {"$set": update_fields}
                        )
                        updated_count += 1
            
            logger.info(f"Updated {updated_count} schemas with organization_id/name")
            
            # Remove fields from all schema_revisions
            result = await db.schema_revisions.update_many(
                {"$or": [
                    {"name": {"$exists": True}},
                    {"organization_id": {"$exists": True}}
                ]},
                {"$unset": {
                    "name": "",
                    "organization_id": ""
                }}
            )
            
            logger.info(f"Removed fields from {result.modified_count} schema_revisions")
            
            return True
            
        except Exception as e:
            logger.error(f"Schema organization ID migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """Restore organization_id and name from schemas to schema_revisions"""
        try:
            # For each schema, copy its organization_id back to all matching schema_revisions
            schemas_cursor = db.schemas.find({
                "$or": [
                    {"name": {"$exists": True}},
                    {"organization_id": {"$exists": True}}
                ]
            })
            
            restored_count = 0
            async for schema in schemas_cursor:
                schema_id = schema.get("_id")
                update_fields = {}
                
                if "name" in schema:
                    update_fields["name"] = schema["name"]
                
                if "organization_id" in schema:
                    update_fields["organization_id"] = schema["organization_id"]
                
                if update_fields:
                    # Find all revisions for this schema
                    result = await db.schema_revisions.update_many(
                        {"schema_id": str(schema_id)},
                        {"$set": update_fields}
                    )
                    
                    restored_count += result.modified_count
            
            logger.info(f"Restored fields for {restored_count} schema_revisions")
            return True
            
        except Exception as e:
            logger.error(f"Schema organization ID migration revert failed: {e}")
            return False

# Add this new migration class before the MIGRATIONS list
class AddPdfIdToDocuments(Migration):
    def __init__(self):
        super().__init__("Add pdf_id to documents and convert non-PDFs to PDF")

    async def up(self, db):
        analytiq_client = ad.common.get_analytiq_client()

        docs = db["docs"]
        files = db["files.files"]
        async for doc in docs.find({}):
            if "pdf_id" in doc:
                continue  # Already migrated

            file_name = doc["mongo_file_name"]
            file_ext = os.path.splitext(file_name)[1].lower()
            mime_type = ad.common.doc.EXTENSION_TO_MIME.get(file_ext)
            if mime_type == "application/pdf":
                pdf_id = doc["document_id"]
                pdf_file_name = file_name
            else:
                # Download original file
                file_blob = await ad.common.get_file_async(analytiq_client, file_name)["blob"]
                # Convert to PDF
                pdf_blob = ad.common.file.convert_to_pdf(file_blob, file_ext)
                pdf_id = ad.common.create_id()
                pdf_file_name = f"{pdf_id}.pdf"
                # Save PDF file
                await ad.common.save_file_async(analytiq_client, pdf_file_name, pdf_blob, {
                    "name": pdf_file_name,
                    "type": "application/pdf",
                    "size": len(pdf_blob),
                    "created_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC)
                })

            # Update document
            await docs.update_one(
                {"_id": doc["_id"]},
                {"$set": {"pdf_id": pdf_id, "pdf_file_name": pdf_file_name}}
            )
        return True

    async def down(self, db):
        await db["docs"].update_many({}, {"$unset": {"pdf_id": "", "pdf_file_name": ""}})
        return True

# Add this new migration class before the MIGRATIONS list
class RenamePromptIdToPromptRevId(Migration):
    def __init__(self):
        super().__init__(description="Rename prompt_id to prompt_rev_id in llm.runs collection")

    async def up(self, db) -> bool:
        try:
            # Update all documents in llm.runs collection
            result = await db["llm.runs"].update_many(
                {"prompt_id": {"$exists": True}},
                [
                    {
                        "$set": {
                            "prompt_rev_id": "$prompt_id",
                            "prompt_id": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Updated {result.modified_count} documents in llm.runs collection")
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    async def down(self, db) -> bool:
        try:
            # Revert the changes
            result = await db["llm.runs"].update_many(
                {"prompt_rev_id": {"$exists": True}},
                [
                    {
                        "$set": {
                            "prompt_id": "$prompt_rev_id",
                            "prompt_rev_id": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Reverted {result.modified_count} documents in llm.runs collection")
            return True
        except Exception as e:
            logger.error(f"Migration revert failed: {e}")
            return False

# Add this new migration class before the MIGRATIONS list
class RenameLlmRunsCollection(Migration):
    def __init__(self):
        super().__init__(description="Rename llm.runs collection to llm_runs")
        
    async def up(self, db) -> bool:
        """Rename llm.runs collection to llm_runs"""
        try:
            # Create new collection with data from old one
            llm_runs_cursor = db["llm.runs"].find({})
            async for doc in llm_runs_cursor:
                await db.llm_runs.insert_one(doc)
            
            # Drop the old collection
            await db["llm.runs"].drop()
            
            logger.info("Successfully renamed llm.runs collection to llm_runs")
            return True
            
        except Exception as e:
            logger.error(f"Collection rename migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """Revert collection renaming: llm_runs → llm.runs"""
        try:
            # Create old collection with data from new one
            llm_runs_cursor = db.llm_runs.find({})
            async for doc in llm_runs_cursor:
                await db["llm.runs"].insert_one(doc)
            
            # Drop the new collection
            await db.llm_runs.drop()
            
            logger.info("Successfully reverted llm_runs collection back to llm.runs")
            return True
            
        except Exception as e:
            logger.error(f"Collection rename migration revert failed: {e}")
            return False

# Add this new migration class before the MIGRATIONS list
class RemoveLlmModelsAndTokens(Migration):
    def __init__(self):
        super().__init__(description="Remove llm_models and llm_tokens collections")
        
    async def up(self, db) -> bool:
        """Remove llm_models and llm_tokens collections"""
        try:
            # Drop the collections if they exist
            collections = await db.list_collection_names()
            
            if "llm_models" in collections:
                await db.llm_models.drop()
                logger.info("Dropped llm_models collection")
                
            if "llm_tokens" in collections:
                await db.llm_tokens.drop()
                logger.info("Dropped llm_tokens collection")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove collections: {e}")
            return False
    
    async def down(self, db) -> bool:
        """
        Cannot restore the collections as we don't have the original data.
        This is a one-way migration.
        """
        logger.warning("Cannot restore llm_models and llm_tokens collections as original data is not preserved")
        return False

# Add this new migration class before the MIGRATIONS list
class AddPromptIdAndVersionToLlmRuns(Migration):
    def __init__(self):
        super().__init__(description="Add prompt_id and prompt_version fields to llm_runs collection")
        
    async def up(self, db) -> bool:
        """Add prompt_id and prompt_version fields to all documents in llm_runs collection"""
        try:
            from bson import ObjectId
            
            # Get all documents in llm_runs that don't have prompt_id or prompt_version
            cursor = db.llm_runs.find({
                "$or": [
                    {"prompt_id": {"$exists": False}},
                    {"prompt_version": {"$exists": False}}
                ]
            })
            
            updated_count = 0
            skipped_count = 0
            error_count = 0
            
            async for doc in cursor:
                prompt_rev_id = doc.get("prompt_rev_id")
                
                if not prompt_rev_id:
                    logger.warning(f"Document {doc['_id']} missing prompt_rev_id, skipping")
                    skipped_count += 1
                    continue
                
                try:
                    # Handle special case for default prompt
                    if prompt_rev_id == "default":
                        prompt_id = "default"
                        prompt_version = 1
                    else:
                        # Look up the prompt revision
                        prompt_revision = await db.prompt_revisions.find_one({"_id": ObjectId(prompt_rev_id)})
                        if prompt_revision is None:
                            logger.warning(f"Prompt revision {prompt_rev_id} not found for document {doc['_id']}, skipping")
                            skipped_count += 1
                            continue
                        
                        prompt_id = str(prompt_revision["prompt_id"])
                        prompt_version = prompt_revision["prompt_version"]
                    
                    # Update the document
                    await db.llm_runs.update_one(
                        {"_id": doc["_id"]},
                        {
                            "$set": {
                                "prompt_id": prompt_id,
                                "prompt_version": prompt_version
                            }
                        }
                    )
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing document {doc['_id']}: {e}")
                    error_count += 1
                    continue
            
            logger.info(f"Migration completed: {updated_count} documents updated, {skipped_count} skipped, {error_count} errors")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """Remove prompt_id and prompt_version fields from llm_runs collection"""
        try:
            result = await db.llm_runs.update_many(
                {
                    "$or": [
                        {"prompt_id": {"$exists": True}},
                        {"prompt_version": {"$exists": True}}
                    ]
                },
                {
                    "$unset": {
                        "prompt_id": "",
                        "prompt_version": ""
                    }
                }
            )
            
            logger.info(f"Removed prompt_id and prompt_version fields from {result.modified_count} documents")
            return True
            
        except Exception as e:
            logger.error(f"Migration revert failed: {e}")
            return False

# Add this new migration class before the MIGRATIONS list
class RenameAwsCredentialsCollection(Migration):
    def __init__(self):
        super().__init__(description="Rename aws_credentials collection to aws_config")
        
    async def up(self, db) -> bool:
        """Rename aws_credentials collection to aws_config"""
        try:
            # Check if aws_credentials collection exists
            collections = await db.list_collection_names()
            
            if "aws_credentials" in collections:
                # Create new collection with data from old one
                aws_credentials_cursor = db.aws_credentials.find({})
                async for doc in aws_credentials_cursor:
                    await db.aws_config.insert_one(doc)
                
                # Drop the old collection
                await db.aws_credentials.drop()
                
                logger.info("Successfully renamed aws_credentials collection to aws_config")
            else:
                logger.info("aws_credentials collection not found, skipping migration")
            
            return True
            
        except Exception as e:
            logger.error(f"Collection rename migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """Revert collection renaming: aws_config → aws_credentials"""
        try:
            # Check if aws_config collection exists
            collections = await db.list_collection_names()
            
            if "aws_config" in collections:
                # Create old collection with data from new one
                aws_config_cursor = db.aws_config.find({})
                async for doc in aws_config_cursor:
                    await db.aws_credentials.insert_one(doc)
                
                # Drop the new collection
                await db.aws_config.drop()
                
                logger.info("Successfully reverted aws_config collection back to aws_credentials")
            else:
                logger.info("aws_config collection not found, skipping revert")
            
            return True
            
        except Exception as e:
            logger.error(f"Collection rename migration revert failed: {e}")
            return False

class RenamePromptRevIdToPromptRevid(Migration):
    def __init__(self):
        super().__init__(description="Rename prompt_rev_id to prompt_revid in llm_runs collection")

    async def up(self, db) -> bool:
        try:
            # Update documents that have prompt_rev_id
            result = await db.llm_runs.update_many(
                {"prompt_rev_id": {"$exists": True}},
                [
                    {
                        "$set": {
                            "prompt_revid": "$prompt_rev_id",
                            "prompt_rev_id": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Renamed prompt_rev_id to prompt_revid in {result.modified_count} llm_runs documents")
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    async def down(self, db) -> bool:
        try:
            # Revert documents that have prompt_revid
            result = await db.llm_runs.update_many(
                {"prompt_revid": {"$exists": True}},
                [
                    {
                        "$set": {
                            "prompt_rev_id": "$prompt_revid",
                            "prompt_revid": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Reverted prompt_revid to prompt_rev_id in {result.modified_count} llm_runs documents")
            return True
        except Exception as e:
            logger.error(f"Migration revert failed: {e}")
            return False

class RenameUserFields(Migration):
    def __init__(self):
        super().__init__(description="Rename user fields to snake_case: emailVerified, hasSeenTour, createdAt, hasPassword")

    async def up(self, db) -> bool:
        try:
            # Update documents that have emailVerified, hasSeenTour, createdAt, or hasPassword
            result1 = await db.users.update_many(
                {"emailVerified": {"$exists": True}},
                [
                    {
                        "$set": {
                            "email_verified": "$emailVerified",
                            "emailVerified": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Renamed emailVerified to email_verified in {result1.modified_count} users documents")

            result2 = await db.users.update_many(
                {"hasSeenTour": {"$exists": True}},
                [
                    {
                        "$set": {
                            "has_seen_tour": "$hasSeenTour",
                            "hasSeenTour": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Renamed hasSeenTour to has_seen_tour in {result2.modified_count} users documents")

            result3 = await db.users.update_many(
                {"createdAt": {"$exists": True}},
                [
                    {
                        "$set": {
                            "created_at": "$createdAt",
                            "createdAt": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Renamed createdAt to created_at in {result3.modified_count} users documents")

            result4 = await db.users.update_many(
                {"hasPassword": {"$exists": True}},
                [
                    {
                        "$set": {
                            "has_password": "$hasPassword",
                            "hasPassword": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Renamed hasPassword to has_password in {result4.modified_count} users documents")

            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    async def down(self, db) -> bool:
        try:
            # Revert documents that have email_verified, has_seen_tour, created_at, or has_password
            result1 = await db.users.update_many(
                {"email_verified": {"$exists": True}},
                [
                    {
                        "$set": {
                            "emailVerified": "$email_verified",
                            "email_verified": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Reverted email_verified to emailVerified in {result1.modified_count} users documents")

            result2 = await db.users.update_many(
                {"has_seen_tour": {"$exists": True}},
                [
                    {
                        "$set": {
                            "hasSeenTour": "$has_seen_tour",
                            "has_seen_tour": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Reverted has_seen_tour to hasSeenTour in {result2.modified_count} users documents")

            result3 = await db.users.update_many(
                {"created_at": {"$exists": True}},
                [
                    {
                        "$set": {
                            "createdAt": "$created_at",
                            "created_at": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Reverted created_at to createdAt in {result3.modified_count} users documents")

            result4 = await db.users.update_many(
                {"has_password": {"$exists": True}},
                [
                    {
                        "$set": {
                            "hasPassword": "$has_password",
                            "has_password": "$$REMOVE"
                        }
                    }
                ]
            )
            logger.info(f"Reverted has_password to hasPassword in {result4.modified_count} users documents")

            return True
        except Exception as e:
            logger.error(f"Migration revert failed: {e}")
            return False

class UpgradeTokens(Migration):
    def __init__(self):
        super().__init__(description="Upgrade specific encrypted fields: aws_config.access_key_id, aws_config.secret_access_key, and llm_providers.token")

    async def upgrade_encrypted_field(self, db, collection_name: str, field_name: str, doc_id_field: str = "_id", doc_name_field: str = None) -> tuple[int, int, int]:
        """Helper method to upgrade a specific encrypted field in a collection"""
        import analytiq_data as ad
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        # Get all documents with the encrypted field
        cursor = db[collection_name].find({field_name: {"$exists": True, "$ne": None, "$ne": ""}})
        
        async for doc in cursor:
            try:
                old_encrypted_value = doc.get(field_name)
                if not old_encrypted_value:
                    skipped_count += 1
                    continue
                
                doc_id = doc.get(doc_id_field)
                doc_name = doc.get(doc_name_field, f"doc_{doc_id}") if doc_name_field else f"doc_{doc_id}"
                
                # Try to decrypt with the fallback method
                try:
                    decrypted_value = ad.crypto.decrypt_token(old_encrypted_value, secret_name="FASTAPI_SECRET")
                except Exception as e:
                    logger.warning(f"Failed to decrypt {field_name} for {doc_name} with FASTAPI_SECRET: {e}")
                    # If fallback fails, try current method (value might already be upgraded)
                    try:
                        decrypted_value = ad.crypto.decrypt_token(old_encrypted_value)
                        logger.info(f"{field_name} for {doc_name} is already using current encryption method")
                        skipped_count += 1
                        continue
                    except Exception as e2:
                        logger.error(f"Failed to decrypt {field_name} for {doc_name} with both methods: {e2}")
                        error_count += 1
                        continue
                
                # Re-encrypt with the current method
                new_encrypted_value = ad.crypto.encrypt_token(decrypted_value)
                
                # Update the document with the new encrypted value
                await db[collection_name].update_one(
                    {doc_id_field: doc_id},
                    {"$set": {field_name: new_encrypted_value}}
                )
                
                updated_count += 1
                logger.info(f"Successfully upgraded {field_name} for {doc_name}")
                
            except Exception as e:
                logger.error(f"Error processing {field_name} for {doc_name}: {e}")
                error_count += 1
                continue
        
        return updated_count, skipped_count, error_count

    async def up(self, db) -> bool:
        """Upgrade exactly 3 specific encrypted fields by decrypting with decrypt_token_fallback() and re-encrypting with encrypt_token()"""
        try:
            total_updated = 0
            total_skipped = 0
            total_errors = 0
            
            # 1. Upgrade aws_config.access_key_id
            logger.info("Upgrading aws_config.access_key_id...")
            updated, skipped, errors = await self.upgrade_encrypted_field(
                db, "aws_config", "access_key_id", "_id", "user_id"
            )
            total_updated += updated
            total_skipped += skipped
            total_errors += errors
            logger.info(f"aws_config.access_key_id: {updated} upgraded, {skipped} skipped, {errors} errors")
            
            # 2. Upgrade aws_config.secret_access_key
            logger.info("Upgrading aws_config.secret_access_key...")
            updated, skipped, errors = await self.upgrade_encrypted_field(
                db, "aws_config", "secret_access_key", "_id", "user_id"
            )
            total_updated += updated
            total_skipped += skipped
            total_errors += errors
            logger.info(f"aws_config.secret_access_key: {updated} upgraded, {skipped} skipped, {errors} errors")
            
            # 3. Upgrade llm_providers.token
            logger.info("Upgrading llm_providers.token...")
            updated, skipped, errors = await self.upgrade_encrypted_field(
                db, "llm_providers", "token", "_id", "name"
            )
            total_updated += updated
            total_skipped += skipped
            total_errors += errors
            logger.info(f"llm_providers.token: {updated} upgraded, {skipped} skipped, {errors} errors")
            
            logger.info(f"UpgradeTokens migration completed: {total_updated} total upgraded, {total_skipped} total skipped, {total_errors} total errors")
            return True
            
        except Exception as e:
            logger.error(f"UpgradeTokens migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        """
        Cannot revert this migration as we don't know which tokens were originally encrypted
        with the fallback method vs the current method. This is a one-way migration.
        """
        logger.warning("Cannot revert UpgradeTokens migration as original encryption method is not preserved")
        return False

class AddAccessTokenUniquenessIndex(Migration):
    def __init__(self):
        super().__init__(description="Add unique index on access_tokens.token field to ensure global token uniqueness")

    async def up(self, db) -> bool:
        """Add unique index on access_tokens.token field"""
        try:
            # Create unique index on the token field
            await db.access_tokens.create_index("token", unique=True)
            logger.info("Successfully created unique index on access_tokens.token field")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create unique index on access_tokens.token: {e}")
            return False
    
    async def down(self, db) -> bool:
        """Remove unique index on access_tokens.token field"""
        try:
            # Drop the unique index
            await db.access_tokens.drop_index("token_1")
            logger.info("Successfully removed unique index on access_tokens.token field")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove unique index on access_tokens.token: {e}")
            return False


class AddWebhookDeliveriesIndexes(Migration):
    def __init__(self):
        super().__init__(description="Add indexes for webhook_deliveries (org queries and retry scanning)")

    async def up(self, db) -> bool:
        try:
            # For org-scoped delivery listing (UI)
            await db.webhook_deliveries.create_index(
                [("organization_id", 1), ("created_at", -1)],
                name="webhook_deliveries_org_created_at",
            )
            # For retry scanning / claiming due deliveries
            await db.webhook_deliveries.create_index(
                [("status", 1), ("next_attempt_at", 1)],
                name="webhook_deliveries_status_next_attempt_at",
            )
            logger.info("Successfully created webhook_deliveries indexes")
            return True
        except Exception as e:
            logger.error(f"Failed to create webhook_deliveries indexes: {e}")
            return False

    async def down(self, db) -> bool:
        try:
            await db.webhook_deliveries.drop_index("webhook_deliveries_org_created_at")
            await db.webhook_deliveries.drop_index("webhook_deliveries_status_next_attempt_at")
            logger.info("Successfully removed webhook_deliveries indexes")
            return True
        except Exception as e:
            logger.error(f"Failed to remove webhook_deliveries indexes: {e}")
            return False


class AddQueueAndCollectionIndexes(Migration):
    """Add indexes for queue collections, document_index, and docs to optimize common queries."""

    def __init__(self):
        super().__init__(
            description="Add indexes for queue polling, document_index lookups, and docs listing"
        )

    async def up(self, db) -> bool:
        try:
            # 1. Queue collections: compound index on {status, created_at} for
            #    find_one_and_update({status: "pending"}, sort: {created_at: 1})
            #    Include static queues + any dynamic queues.kb_index_* collections
            queue_collections = ["queues.ocr", "queues.llm", "queues.webhook"]
            all_collections = await db.list_collection_names()
            for coll_name in all_collections:
                if coll_name.startswith("queues.kb_index_") and coll_name not in queue_collections:
                    queue_collections.append(coll_name)
            for coll_name in queue_collections:
                await db[coll_name].create_index(
                    [("status", 1), ("created_at", 1)],
                    name="status_created_at_idx",
                    background=True,
                )
            logger.info("Created queue indexes for %s", queue_collections)

            # 2. document_index: compound unique index on {kb_id, document_id}
            #    Used by upserts, deletes, find_one lookups
            await db.document_index.create_index(
                [("kb_id", 1), ("document_id", 1)],
                unique=True,
                name="kb_id_document_id_unique_idx",
                background=True,
            )
            # Also index document_id alone for cascade-delete lookups
            await db.document_index.create_index(
                [("document_id", 1)],
                name="document_id_idx",
                background=True,
            )
            logger.info("Created document_index indexes")

            # 3. docs: compound index on {organization_id, upload_date desc}
            #    Used by paginated listing: find({organization_id: ...}).sort("upload_date", -1)
            await db.docs.create_index(
                [("organization_id", 1), ("upload_date", -1)],
                name="org_upload_date_idx",
                background=True,
            )
            logger.info("Created docs org_upload_date_idx index")

            # 4. llm_runs: compound index for fallback lookup
            #    find_one({document_id, prompt_id}, sort: {prompt_version: -1})
            await db.llm_runs.create_index(
                [("document_id", 1), ("prompt_id", 1), ("prompt_version", -1)],
                name="doc_prompt_version_idx",
                background=True,
            )
            # llm_runs: compound index for exact revision lookup
            #    find_one({document_id, prompt_revid}, sort: {_id: -1})
            await db.llm_runs.create_index(
                [("document_id", 1), ("prompt_revid", 1)],
                name="doc_prompt_revid_idx",
                background=True,
            )
            logger.info("Created llm_runs indexes")

            return True
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            return False

    async def down(self, db) -> bool:
        try:
            all_collections = await db.list_collection_names()
            queue_collections = [c for c in all_collections if c.startswith("queues.")]
            for coll_name in queue_collections:
                try:
                    await db[coll_name].drop_index("status_created_at_idx")
                except Exception:
                    pass  # Collection may not exist or index not present
            await db.document_index.drop_index("kb_id_document_id_unique_idx")
            await db.document_index.drop_index("document_id_idx")
            await db.docs.drop_index("org_upload_date_idx")
            await db.llm_runs.drop_index("doc_prompt_version_idx")
            await db.llm_runs.drop_index("doc_prompt_revid_idx")
            logger.info("Successfully removed queue/document_index/docs/llm_runs indexes")
            return True
        except Exception as e:
            logger.error(f"Failed to remove indexes: {e}")
            return False


# List of all migrations in order
MIGRATIONS = [
    OcrKeyMigration(),
    LlmResultFieldsMigration(),
    SchemaJsonSchemaMigration(),
    RenameJsonSchemaToResponseFormat(),
    RemoveSchemaFormatField(),
    AddStableIdentifiers(),
    RenamePromptVersion(),
    RenameSchemaVersion(),
    RemoveSchemaNameField(),
    RenameCollections(),
    UseMongoObjectIDs(),
    MigratePromptNames(),
    MigratePromptOrganizationIDs(),
    MigrateSchemaOrganizationIDs(),
    AddPdfIdToDocuments(),
    RenamePromptIdToPromptRevId(),
    RenameLlmRunsCollection(),
    RemoveLlmModelsAndTokens(),
    AddPromptIdAndVersionToLlmRuns(),
    RenameAwsCredentialsCollection(),
    RenamePromptRevIdToPromptRevid(),
    RenameUserFields(),
    UpgradeTokens(),
    AddAccessTokenUniquenessIndex(),
    AddWebhookDeliveriesIndexes(),
    AddQueueAndCollectionIndexes(),
    # Add more migrations here
]

# Set versions based on position in list
for i, migration in enumerate(MIGRATIONS, start=1):
    migration.version = i 