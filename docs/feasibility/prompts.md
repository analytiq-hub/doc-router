# Prompt System Refactoring Feasibility Study

## Overview

This document explores the feasibility of refactoring the prompt system to improve naming conventions and introduce a template-based architecture. The goal is to minimize schema changes while enhancing the system's extensibility and understandability.

## Current System

The current implementation has two main collections:
- `prompts`: Contains all prompt instances with a version field
- `prompt_versions`: Tracks the latest version number for each prompt

Issues with the current approach:
- The naming is confusing as `prompts` contains versions while `prompt_versions` tracks IDs
- There's no standardized way to define reusable prompt templates
- The versioning system lacks clarity in terms of its entity relationships

## Proposed Changes

### 1. Database Schema Refactoring

#### 1.1 Collection Renaming

```
prompts → prompt_revisions
prompt_versions → prompts
```

This rename better reflects that:
- `prompt_revisions` contains the actual content and implementation of each prompt version
- `prompts` simply tracks name and latest version number for each prompt ID

The prompt name should be moved to `prompts`.

#### 1.2 Schema Adjustments

Add a simple boolean field to indicate templates:
```json
{
  "is_template": true|false,
}
```

### 2. API Changes

#### 2.1 Endpoint Structure

Maintain backward compatibility with naming while adding template functionality:

```
# Existing endpoints remain unchanged
/v0/orgs/{organization_id}/prompts
/v0/orgs/{organization_id}/prompts/{prompt_id}

# New template endpoints
/v0/orgs/{organization_id}/prompt_templates
/v0/orgs/{organization_id}/prompt_templates/{template_id}
```

#### 2.2 API Specifications

**Template Endpoints:**

```
GET /v0/orgs/{organization_id}/prompt_templates
- Lists all available templates
- Query params: skip, limit, tag_ids
- Response: ListTemplatesResponse (same structure as ListPromptsResponse)

GET /v0/orgs/{organization_id}/prompt_templates/{template_id}
- Gets a specific template with full content
- Response: PromptTemplate model (same structure as Prompt)
```

### 3. Frontend Changes

#### 3.1 UI Components

- Add a `PromptTemplates.tsx` component for browsing templates
- Add template selection in prompt creation flow
- Create a "Use Template" button that pre-fills prompt creation form

#### 3.2 TypeScript Types

Update in `packages/typescript/frontend/src/types/prompts.ts`:
```typescript
export interface PromptConfig {
  name: string;
  content: string;
  schema_id?: string;
  schema_version?: number;
  tag_ids?: string[];
  model?: string;
  is_template?: boolean;
}

export interface PromptTemplateConfig extends PromptConfig {
  is_template: true;
}

// Add template-specific API interfaces
export interface ListTemplatesParams {
  organizationId: string;
  skip?: number;
  limit?: number;
  tag_ids?: string;
}

export interface GetTemplateParams {
  organizationId: string;
  templateId: string;
}
```

### 4. docrouter_sdk Changes

Update client library in `packages/python/sdk/`:

```python
# Update models in packages/python/sdk/src/docrouter_sdk/models/prompt.py
class PromptConfig(BaseModel):
    name: str
    content: str
    schema_id: Optional[str] = None
    schema_version: Optional[int] = None
    tag_ids: List[str] = []
    model: str = "gpt-4o-mini"
    is_template: bool = False

# Add template methods to packages/python/sdk/src/docrouter_sdk/api/prompts.py
class PromptTemplatesAPI:
    def list(self, organization_id: str, skip: int = 0, limit: int = 10, tag_ids: List[str] = None) -> ListTemplatesResponse:
        """List prompt templates"""
        ...

    def get(self, organization_id: str, template_id: str) -> PromptTemplate:
        """Get a specific prompt template"""
        ...

```

### 5. Git-Based Templates

Implement system for loading templates from Git repository:

```
/templates/prompts/*.json → Stores templates as JSON files
```

Template JSON format:
```json
{
  "name": "Template Name",
  "content": "Template content with {{variables}}",
  "schema_id": "optional-schema-id", 
  "model": "gpt-4o-mini",
  "tag_ids": ["tag1", "tag2"]
}
```

Add startup code to load templates:
```python
async def lifespan(app):
    # Existing startup code
    
    # Load prompt templates from Git
    await load_templates_from_git(db)
    
    yield
    
    # Existing shutdown code
```
### 6. Unit Tests

Update existing tests and add new ones:
- Update collection references from `prompts` to `prompt_definitions`
- Add tests for template listing and retrieval
- Add tests for template instantiation 
- Add tests for Git-based template loading
- Test system vs. user template permissions

## Implementation Plan

1. Create database migration for collection renaming
2. Add is_template and source fields
3. Implement template API endpoints
4. Implement Git-based template loading
5. Create template UI components
6. Update docrouter_sdk
7. Add template unit tests
8. Deploy with backward compatibility

## Risk Assessment

Low-risk changes:
- Collection renaming (done via migration)
- Adding template fields (optional fields)
- Simple CRUD operations for templates

Medium-risk changes:
- Git integration for templates
- Template instantiation logic
- Frontend template selection UI

## Conclusion

This refactoring is feasible with minimal schema changes. By simply marking templates with a boolean flag rather than tracking parent-child relationships, we maintain a clean data model while adding powerful template functionality.

The implementation separates templates from regular prompts via API endpoints rather than complex database relationships, making the system easier to understand and maintain.
