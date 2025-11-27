from datetime import datetime
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field

class SchemaProperty(BaseModel):
    type: Literal['string', 'integer', 'number', 'boolean', 'array', 'object']
    format: Optional[str] = None
    description: Optional[str] = None
    
class SchemaResponseFormat(BaseModel):
    type: Literal['json_schema']
    json_schema: dict

class SchemaConfig(BaseModel):
    name: str
    response_format: SchemaResponseFormat

class Schema(SchemaConfig):
    schema_revid: str
    schema_id: str
    schema_version: int
    created_at: datetime
    created_by: str

class ListSchemasResponse(BaseModel):
    schemas: List[Schema]
    total_count: int
    skip: int
