# Database Migrations Guide

This document explains how to create and manage database migrations in the Analytiq project.

## Overview

The migration system allows you to make changes to the database schema in a versioned and reversible way. Each migration has an `up()` method to apply changes and a `down()` method to revert them.

## MongoDB indexes

Index creation and updates are **not** managed by adding new versioned migrations for every index change. See [`docs/indexes.md`](../../../docs/indexes.md) for the full policy.

- **Deploy / migrate:** `run_migrations()` runs `reconcile_indexes()` under the migration lock on every deploy (registry in `analytiq_data/mongodb/index_registry.py`).
- **Backend lifespan:** `ensure_runtime_indexes()` create-only safety net when migrate was skipped (local dev).
- **New indexes:** add an `IndexSpec` to `EXPECTED_INDEXES` in `index_registry.py` — no schema bump required.

Versioned migrations may still contain historical `create_index` calls from before the registry; steady-state deploys rely on reconcile.

## Migration System Structure

- `analytiq_data/migrations/migration.py` - Core migration system
- `analytiq_data/migrations/__init__.py` - Migration exports
- Individual migration classes in `migration.py`
- Migration version tracking in MongoDB's `migrations` collection

## Current Migrations

1. `OcrKeyMigration`: Renames OCR keys from `_list` to `_json`
2. `LlmResultFieldsMigration`: Adds new fields to LLM results (updated_llm_result, is_edited, is_verified, created_at, updated_at)
3. `SchemaJsonSchemaMigration`: Converts schemas from old field format to JsonSchema format
4. `RenameJsonSchemaToResponseFormat`: Renames json_schema field to response_format in schemas collection

## Migration Process

### 1. Create a New Migration

Create a new class in `packages/analytiq_data/migrations/migration.py` that inherits from the `Migration` base class:

```python
class YourMigrationName(Migration):
    def __init__(self):
        super().__init__(description="Brief description of what this migration does")

    async def up(self, db) -> bool:
        try:
            # Implement your migration logic here
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    async def down(self, db) -> bool:
        try:
            # Implement your rollback logic here
            return True
        except Exception as e:
            logger.error(f"Migration revert failed: {e}")
            return False
```

### 2. Register the Migration

Add your migration to the `MIGRATIONS` list in `packages/analytiq_data/migrations/migration.py`. The version number will be automatically assigned based on the position in the list:

```python
MIGRATIONS = [
    ExistingMigration(),
    YourMigrationName(),  # Will get the next version number automatically
]
```

### 3. Testing Migrations

1. Test the upgrade path:
   ```python
   await ad.migrations.run_migrations(analytiq_client)
   ```

2. Test the downgrade path:
   ```python
   await ad.migrations.run_migrations(analytiq_client, target_version=1)
   ```

## Migration Examples

### Example 1: Renaming Fields

```python
class RenameFieldMigration(Migration):
    def __init__(self):
        super().__init__(
            version=2,
            description="Rename user.name to user.full_name"
        )
    async def up(self, db) -> bool:
        try:
            await db.users.update_many(
                {},
                {"$rename": {"name": "full_name"}}
            )
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    async def down(self, db) -> bool:
        try:
            await db.users.update_many(
                {},
                {"$rename": {"full_name": "name"}}
            )
            return True
        except Exception as e:
            logger.error(f"Migration revert failed: {e}")
            return False
```

### Example 2: Adding a New Field

```python
class AddNewFieldMigration(Migration):
    def __init__(self):
        super().__init__(
            version=3,
            description="Add new_field to user collection"
        )
    async def up(self, db) -> bool:
        try:
            await db.users.update_many(
                {},
                {"$addFields": {"new_field": "new_value"}}
            )
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    async def down(self, db) -> bool:
        try:
            await db.users.update_many(
                {},
                {"$unset": {"new_field": ""}}
            )
            return True
        except Exception as e:
            logger.error(f"Migration revert failed: {e}")
            return False
```

## Best Practices

1. **Version Numbers**: Always increment version numbers sequentially.
2. **Atomic Changes**: Each migration should make one logical change.
3. **Idempotency**: Migrations should be idempotent (can be run multiple times safely).
4. **Testing**: Test both `up` and `down` migrations before deploying.
5. **Documentation**: Include clear descriptions of what each migration does.
6. **Error Handling**: Always include proper error handling and logging.
7. **Backup**: Always backup your database before running migrations in production.

## Troubleshooting

If a migration fails:

1. Check the logs for detailed error messages
2. Fix any issues in the migration code
3. Revert to the previous version if needed:
   ```python
   await ad.migrations.run_migrations(analytiq_client, target_version=previous_version)
   ```
4. Try the migration again after fixing the issues

## Database Backup Tool

The project includes a standalone backup script (`backup_db.py`) that allows you to copy databases between MongoDB instances.

### Usage

The backup script can be run in two modes:

1. Backup to different database on the same MongoDB instance:
```bash
python backup_db.py --src-uri "mongodb://localhost:27017" --src "source_db" --dest "backup_db"
```

2. Backup between different MongoDB instances:
```bash
python backup_db.py --src-uri "mongodb://source-server:27017" --dest-uri "mongodb://backup-server:27017" --src "source_db" --dest "backup_db"
```

### Arguments

- `--src-uri`: (Required) Source MongoDB connection URI
- `--dest-uri`: (Optional) Destination MongoDB connection URI. If not specified, uses the source URI
- `--src`: (Required) Source database name
- `--dest`: (Required) Destination database name

### Features

- Copies all collections and their documents
- Supports backup between different MongoDB instances
- Progress tracking for each collection
- Proper connection handling and cleanup
- Prevents accidental overwrite of source database
- Detailed error reporting

### Best Practices

1. Always test the backup process with a small dataset first
2. Ensure sufficient disk space on the destination server
3. Run during low-traffic periods for large databases
4. Verify the backup by checking document counts and sampling data
5. Consider using MongoDB's native tools (mongodump/mongorestore) for very large databases

### Example Output

```
Starting backup from 'source_db' to 'backup_db'
Source URI: mongodb://localhost:27017
Destination URI: mongodb://localhost:27017
Found 5 collections to backup
Backing up collection: users
✓ Copied 1000 documents
Backing up collection: documents
✓ Copied 500 documents
...
Backup completed successfully!
```
