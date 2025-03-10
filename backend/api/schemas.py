from pydantic import BaseModel, Field, constr, ConfigDict, field_validator
from datetime import datetime
from typing import List, Literal, Optional, Any, Dict, Union, ForwardRef
from enum import Enum

# Pydantic models
class User(BaseModel):
    user_id: str
    user_name: str
    token_type: str

class AccessToken(BaseModel):
    id: str
    user_id: str
    organization_id: Optional[str] = None
    name: str
    token: str
    created_at: datetime
    lifetime: int

class ListAccessTokensResponse(BaseModel):
    access_tokens: List[AccessToken]
    
class CreateAccessTokenRequest(BaseModel):
    name: str
    lifetime: int
    organization_id: Optional[str] = None

class DocumentUpload(BaseModel):
    name: str
    content: str
    tag_ids: List[str] = []  # Optional list of tag IDs

class DocumentsUpload(BaseModel):
    documents: List[DocumentUpload]

class DocumentMetadata(BaseModel):
    id: str
    document_name: str
    upload_date: datetime
    uploaded_by: str
    state: str
    tag_ids: List[str] = []  # List of tag IDs

class DocumentResponse(BaseModel):
    metadata: DocumentMetadata
    content: str  # Changed from bytes to str since we're using base64 encoded string

    model_config = ConfigDict(arbitrary_types_allowed=True)

class ListDocumentsResponse(BaseModel):
    documents: List[DocumentMetadata]
    total_count: int
    skip: int

# Add this new model after the DocumentMetadata class
class DocumentUpdate(BaseModel):
    """Schema for updating document metadata"""
    tag_ids: List[str] = Field(
        default=[],
        description="List of tag IDs associated with the document"
    )

class LLMModel(BaseModel):
    id: str
    name: str
    provider: str
    description: str
    max_tokens: int
    cost_per_1m_input_tokens: float
    cost_per_1m_output_tokens: float

class ListLLMModelsResponse(BaseModel):
    models: List[LLMModel]

class LLMToken(BaseModel):
    id: str
    user_id: str
    llm_vendor: Literal["OpenAI", "Anthropic", "Gemini", "Groq", "Mistral"]
    token: str
    created_at: datetime

class CreateLLMTokenRequest(BaseModel):
    llm_vendor: Literal["OpenAI", "Anthropic", "Gemini", "Groq", "Mistral"]
    token: str

class ListLLMTokensResponse(BaseModel):
    llm_tokens: List[LLMToken]

class AWSCredentials(BaseModel):
    access_key_id: str
    secret_access_key: str

class GetOCRMetadataResponse(BaseModel):
    n_pages: int
    ocr_date: str

class LLMRunResponse(BaseModel):
    status: str
    result: dict

class LLMResult(BaseModel):
    prompt_id: str
    document_id: str
    llm_result: dict
    updated_llm_result: dict
    is_edited: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

class UpdateLLMResultRequest(BaseModel):
    updated_llm_result: dict
    is_verified: bool = False

class JsonSchemaProperty(BaseModel):
    type: Literal['string', 'integer', 'number', 'boolean', 'array', 'object']
    format: str | None = None
    description: str | None = None
    items: ForwardRef('JsonSchemaProperty') | None = None
    properties: Dict[str, ForwardRef('JsonSchemaProperty')] | None = None

class ResponseFormat(BaseModel):
    type: Literal['json_schema']
    json_schema: dict = Field(
        ..., 
        json_schema_extra={
            "example": {
                "name": "document_extraction",
                "schema": {
                    "type": "object",
                    "properties": {
                        "invoice_date": {
                            "type": "string",
                            "description": "invoice date"
                        }
                    },
                    "required": ["invoice_date"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }
    )

    @field_validator('json_schema')
    def validate_json_schema(cls, v):
        # Validate schema follows OpenAI format
        required_keys = {'name', 'schema', 'strict'}
        if not all(key in v for key in required_keys):
            raise ValueError(f"JSON schema must contain all required keys: {required_keys}")
        
        schema = v['schema']
        if schema.get('type') != 'object':
            raise ValueError("Schema root must be of type 'object'")
            
        if 'properties' not in schema:
            raise ValueError("Schema must contain 'properties'")
            
        if 'required' not in schema:
            raise ValueError("Schema must contain 'required' field")
            
        if 'additionalProperties' not in schema:
            raise ValueError("Schema must specify 'additionalProperties'")
            
        return v

class SchemaConfig(BaseModel):
    name: str
    response_format: ResponseFormat
    is_template: bool = False

class Schema(SchemaConfig):
    id: str
    version: int
    created_at: datetime
    created_by: str
    parent_id: Optional[str] = None

class ListSchemasResponse(BaseModel):
    schemas: List[Schema]
    total_count: int
    skip: int

# Add these new models
class PromptConfig(BaseModel):
    name: str
    content: str
    schema_name: Optional[str] = None
    schema_version: Optional[int] = None
    tag_ids: List[str] = []
    model: str = "gpt-4o-mini"
    is_template: bool = False

class Prompt(PromptConfig):
    id: str
    version: int
    created_at: datetime
    created_by: str
    parent_id: Optional[str] = None

class ListPromptsResponse(BaseModel):
    prompts: List[Prompt]
    total_count: int
    skip: int

# Add these new models for tag management
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

# Add to schemas.py
class OrganizationMember(BaseModel):
    user_id: str
    role: Literal['admin', 'user']

# Add this new type definition near the top with other Literal types
OrganizationType = Literal["individual", "team", "enterprise"]

class OrganizationCreate(BaseModel):
    name: str
    type: OrganizationType = "individual"

class OrganizationUpdate(BaseModel):
    name: str | None = None
    type: OrganizationType = "individual"
    members: List[OrganizationMember] | None = None

class Organization(BaseModel):
    id: str
    name: str
    members: List[OrganizationMember]
    type: OrganizationType = "individual"
    created_at: datetime
    updated_at: datetime

class ListOrganizationsResponse(BaseModel):
    organizations: List[Organization]

# Add these new models after the existing ones
class UserCreate(BaseModel):
    email: str
    name: str
    password: str

class UserUpdate(BaseModel):
    name: str | None = None
    password: str | None = None
    role: str | None = None  # Replace isAdmin with role
    emailVerified: bool | None = None
    hasSeenTour: bool | None = None

class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    emailVerified: bool | None
    createdAt: datetime
    hasPassword: bool
    hasSeenTour: bool | None = None

class ListUsersResponse(BaseModel):
    users: List[UserResponse]
    total_count: int
    skip: int

class InvitationStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    expired = "expired"

class CreateInvitationRequest(BaseModel):
    email: str
    organization_id: Optional[str] = None  # For future use

class InvitationResponse(BaseModel):
    id: str
    email: str
    status: InvitationStatus
    expires: datetime
    created_by: str
    created_at: datetime
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    user_exists: Optional[bool] = None

class ListInvitationsResponse(BaseModel):
    invitations: list[InvitationResponse]
    total_count: int
    skip: int

# Add this to your OrganizationType documentation if you have it
class OrganizationType(str, Enum):
    """
    Organization type with upgrade restrictions:
    - individual can upgrade to team or enterprise
    - team can upgrade to enterprise
    - enterprise cannot be downgraded
    """
    INDIVIDUAL = "individual"
    TEAM = "team"
    ENTERPRISE = "enterprise"

class AcceptInvitationRequest(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None

# Add these new models for flow management
class Position(BaseModel):
    x: float
    y: float

class FlowNode(BaseModel):
    id: str
    type: str
    position: Position
    data: dict

class FlowEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None

class FlowConfig(BaseModel):
    name: str
    description: Optional[str] = None
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    tag_ids: Optional[List[str]] = None

class Flow(FlowConfig):
    id: str
    version: int
    created_at: datetime
    created_by: str

class FlowMetadata(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    version: int
    created_at: datetime
    created_by: str
    tag_ids: Optional[List[str]] = None

class ListFlowsResponse(BaseModel):
    flows: List[FlowMetadata]
    total_count: int
    skip: int
