from pydantic import BaseModel, Field, constr, ConfigDict, field_validator, model_validator
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

class DocumentUpload(BaseModel):
    name: str
    content: str
    tag_ids: List[str] = []  # Optional list of tag IDs
    metadata: Optional[Dict[str, str]] = {}  # Optional key-value metadata pairs

class DocumentsUpload(BaseModel):
    documents: List[DocumentUpload]

class DocumentMetadata(BaseModel):
    id: str
    pdf_id: str
    document_name: str
    upload_date: datetime
    uploaded_by: str
    state: str
    tag_ids: List[str] = []  # List of tag IDs
    type: str | None = None   # MIME type of the returned file (original/pdf)
    metadata: Optional[Dict[str, str]] = {}  # Optional key-value metadata pairs

class DocumentResponse(BaseModel):
    id: str
    pdf_id: str
    document_name: str
    upload_date: datetime
    uploaded_by: str
    state: str
    tag_ids: List[str] = []  # List of tag IDs
    type: str | None = None   # MIME type of the returned file (original/pdf)
    metadata: Optional[Dict[str, str]] = {}  # Optional key-value metadata pairs
    content: str  # Base64 encoded content

    model_config = ConfigDict(arbitrary_types_allowed=True)

class ListDocumentsResponse(BaseModel):
    documents: List[DocumentMetadata]
    total_count: int
    skip: int

# Add this new model after the DocumentMetadata class
class DocumentUpdate(BaseModel):
    """Schema for updating document metadata"""
    document_name: Optional[str] = Field(
        default=None,
        description="New name for the document"
    )
    tag_ids: Optional[List[str]] = Field(
        default=None,
        description="List of tag IDs associated with the document"
    )
    metadata: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional key-value metadata pairs"
    )

class LLMModel(BaseModel):
    litellm_model: str
    litellm_provider: str
    max_input_tokens: int
    max_output_tokens: int
    input_cost_per_token: float
    output_cost_per_token: float

class ListLLMModelsResponse(BaseModel):
    models: List[LLMModel]

class LLMToken(BaseModel):
    id: str
    user_id: str
    llm_vendor: Literal["OpenAI", "Anthropic", "Gemini", "Groq", "Mistral", "xAI"]
    token: str
    created_at: datetime

class LLMProvider(BaseModel):
    name: str
    display_name: str
    litellm_provider: str
    litellm_models_available: List[str]
    litellm_models_enabled: List[str]
    enabled: bool = False
    token: str | None = None
    token_created_at: datetime | None = None

class ListLLMProvidersResponse(BaseModel):
    providers: List[LLMProvider]

class SetLLMProviderConfigRequest(BaseModel):
    litellm_models_enabled: List[str] | None = None
    enabled: bool | None = None
    token: str | None = None

class AWSConfig(BaseModel):
    access_key_id: str
    secret_access_key: str
    s3_bucket_name: str

class GetOCRMetadataResponse(BaseModel):
    n_pages: int
    ocr_date: str

class LLMRunResponse(BaseModel):
    status: str
    result: dict

class LLMResult(BaseModel):
    prompt_revid: str
    prompt_id: str
    prompt_version: int
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

# Add these new models
class PromptConfig(BaseModel):
    name: str
    content: str
    schema_id: Optional[str] = None
    schema_version: Optional[int] = None
    tag_ids: List[str] = []
    model: str = "gpt-4o-mini"

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

class FormResponseFormat(BaseModel):
    json_formio: Optional[List[dict]] = Field(  # Changed from Optional[dict] to Optional[List[dict]]
        default=None,
        description="Form.io schema definition"
    )
    json_formio_mapping: Optional[Dict[str, dict]] = Field(
        default=None,
        description="Field mappings from schema fields to form fields"
    )

    @field_validator('json_formio')
    def validate_json_formio(cls, v):
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("json_formio must be a list")
        return v
    
    @field_validator('json_formio_mapping')
    def validate_json_formio_mapping(cls, v):
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("json_formio_mapping must be a dictionary")
        return v

class FormConfig(BaseModel):
    name: str
    response_format: FormResponseFormat
    tag_ids: List[str] = []  # Add tag_ids field with default empty list

class Form(FormConfig):
    form_revid: str # MongoDB's _id
    form_id: str    # Stable identifier
    form_version: int
    created_at: datetime
    created_by: str

class ListFormsResponse(BaseModel):
    forms: List[Form]
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
    total_count: int
    skip: int

# Add these new models after the existing ones
class UserCreate(BaseModel):
    email: str
    name: str
    password: str

class UserUpdate(BaseModel):
    name: str | None = None
    password: str | None = None
    role: str | None = None  # Replace isAdmin with role
    email_verified: bool | None = None
    has_seen_tour: bool | None = None

class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    email_verified: bool | None
    created_at: datetime
    has_password: bool
    has_seen_tour: bool | None = None

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
    nodes: List[FlowNode]
    edges: List[FlowEdge]
    tag_ids: Optional[List[str]] = None

class Flow(FlowConfig):
    flow_revid: str           # MongoDB's _id
    flow_id: str              # Stable identifier
    flow_version: int
    organization_id: str
    created_at: datetime
    created_by: str
    updated_at: datetime

class ListFlowsResponse(BaseModel):
    flows: List[Flow]
    total_count: int
    skip: int

# Add these new models for LLM testing (admin only)
class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Content of the message")

class LLMPromptRequest(BaseModel):
    model: str = Field(..., description="The LLM model to use (e.g., 'gpt-4o-mini')")
    messages: List[LLMMessage] = Field(..., description="Array of messages for the conversation")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(default=0.7, description="Sampling temperature (0.0 to 2.0)")
    stream: Optional[bool] = Field(default=False, description="Whether to stream the response")

class LLMStreamResponse(BaseModel):
    chunk: str
    done: bool = False

# Add these new models for form submissions
class FormSubmissionData(BaseModel):
    form_revid: str
    submission_data: dict
    submitted_by: Optional[str] = None

class FormSubmission(FormSubmissionData):
    id: str  # MongoDB _id converted to string
    organization_id: str
    created_at: datetime
    updated_at: datetime

# OAuth sign-in models
class OAuthAccountData(BaseModel):
    type: str = "oauth"
    access_token: Optional[str] = None
    expires_at: Optional[int] = None
    token_type: Optional[str] = None
    scope: Optional[str] = None
    id_token: Optional[str] = None
    refresh_token: Optional[str] = None

class OAuthSignInRequest(BaseModel):
    email: str = Field(..., description="User email address")
    name: Optional[str] = Field(None, description="User's full name")
    email_verified: bool = Field(False, description="Whether email is verified")
    provider: Literal["google", "github"] = Field(..., description="OAuth provider")
    provider_account_id: str = Field(..., description="Provider's unique account ID")
    account: OAuthAccountData = Field(..., description="OAuth account data")

class OAuthSignInResponse(BaseModel):
    success: bool
    user_id: str
    is_new_user: bool