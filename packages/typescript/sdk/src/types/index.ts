// Core SDK types
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface DocRouterConfig {
  baseURL: string;
  token?: string;
  tokenProvider?: () => Promise<string>;
  timeout?: number;
  retries?: number;
  onAuthError?: (error: Error) => void;
}

export interface DocRouterAccountConfig {
  baseURL: string;
  accountToken: string;
  timeout?: number;
  retries?: number;
  onAuthError?: (error: Error) => void;
}

export interface DocRouterOrgConfig {
  baseURL: string;
  orgToken: string;
  organizationId: string;
  timeout?: number;
  retries?: number;
  onAuthError?: (error: Error) => void;
}

export interface ApiError extends Error {
  status?: number;
  code?: string;
  details?: unknown;
}

// Auth types
export interface CreateTokenRequest {
  name: string;
  lifetime: number;
}

export interface AccessToken {
  id: string;
  user_id: string;
  organization_id?: string;
  name: string;
  token: string;
  created_at: string;
  lifetime: number;
}

export interface ListAccessTokensResponse {
  access_tokens: AccessToken[];
}

// Organization types
export interface OrganizationMember {
  user_id: string;
  role: 'admin' | 'user';
}

export type OrganizationType = 'individual' | 'team' | 'enterprise';

/** Textract AnalyzeDocument feature types (used when `mode` is `textract`). */
export interface OrgOcrTextractSettings {
  feature_types: string[];
}

/** Reserved for future Mistral OCR options; server uses `mistral-ocr-latest`. */
export type OrgOcrMistralSettings = Record<string, never>;

/** Mistral OCR via Vertex AI (region us-central1, model mistral-ocr-2505). Credentials from GCP cloud_config. */
export type OrgOcrMistralVertexSettings = Record<string, never>;

/** Reserved for future PyMuPDF OCR options; extraction is local embedded text only. */
export type OrgOcrPymupdfSettings = Record<string, never>;

export interface OrgOcrLlmSettings {
  provider: string | null;
  model: string | null;
}

export type OcrMode = 'textract' | 'mistral' | 'mistral_vertex' | 'llm' | 'pymupdf';

export interface OrgOcrConfig {
  mode: OcrMode;
  textract: OrgOcrTextractSettings;
  mistral: OrgOcrMistralSettings;
  mistral_vertex: OrgOcrMistralVertexSettings;
  pymupdf: OrgOcrPymupdfSettings;
  llm: OrgOcrLlmSettings;
}

/** Allowed values for org OCR UI (returned with each organization). */
export interface OrganizationOcrCatalog {
  textract_feature_types: string[];
  modes: string[];
  /** False when Mistral OCR cannot run (Mistral provider off or no models enabled in llm_providers). */
  mistral_enabled?: boolean;
  /** False when GCP credentials are not configured in cloud_config. */
  mistral_vertex_enabled?: boolean;
}

export interface TokenOrganizationResponse {
  organization_id: string | null;
  organization_name: string | null;
  organization_type: OrganizationType | null;
}

export interface Organization {
  id: string;
  name: string;
  type: OrganizationType;
  members: OrganizationMember[];
  default_prompt_enabled?: boolean;
  ocr_config: OrgOcrConfig;
  ocr_catalog: OrganizationOcrCatalog;
  created_at: string;
  updated_at: string;
}

export interface CreateOrganizationRequest {
  name: string;
  type?: OrganizationType;
  default_prompt_enabled?: boolean;
  /** Partial OCR config merged with defaults (same shape as OrgOcrConfig, nested partials allowed). */
  ocr_config?: Record<string, unknown>;
}

export interface UpdateOrganizationRequest {
  name?: string;
  type?: OrganizationType;
  members?: OrganizationMember[];
  default_prompt_enabled?: boolean;
  ocr_config?: Record<string, unknown>;
}

export interface ListOrganizationsResponse {
  organizations: Organization[];
  total_count: number;
  skip: number;
}

// Webhook types

export type WebhookEventType =
  | 'document.uploaded'
  | 'document.error'
  | 'llm.completed'
  | 'llm.error'
  | 'webhook.test';

export type WebhookAuthType = 'hmac' | 'header';

export interface WebhookEndpoint {
  id: string;
  name?: string | null;
  enabled: boolean;
  url: string | null;
  events: WebhookEventType[] | null;
  auth_type: WebhookAuthType;
  auth_header_name?: string | null;
  secret_set: boolean;
  secret_preview?: string | null;
  auth_header_set?: boolean | null;
  auth_header_preview?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  /** Present only once when the server auto-generated a secret on create or update. */
  generated_secret?: string | null;
}

export interface CreateWebhookParams {
  name?: string;
  enabled?: boolean;
  url: string;
  events?: WebhookEventType[];
  auth_type?: WebhookAuthType;
  auth_header_name?: string;
  auth_header_value?: string;
  secret?: string;
}

export interface UpdateWebhookParams {
  webhookId: string;
  name?: string;
  enabled?: boolean;
  url?: string;
  events?: WebhookEventType[];
  auth_type?: WebhookAuthType;
  auth_header_name?: string;
  auth_header_value?: string;
  secret?: string;
}

export interface WebhookDelivery {
  id: string;
  event_id: string;
  event_type: string;
  webhook_id?: string | null;
  status: string;
  attempts: number;
  max_attempts: number;
  document_id?: string | null;
  prompt_revid?: string | null;
  prompt_id?: string | null;
  prompt_version?: number | null;
  last_http_status?: number | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
  next_attempt_at?: string | null;
}

/** Full delivery record from GET .../webhooks/deliveries/{id} (debugging; no secrets). */
export interface WebhookDeliveryDetail extends WebhookDelivery {
  organization_id: string;
  payload: Record<string, unknown>;
  target_url?: string | null;
  auth_type?: string | null;
  auth_header_name?: string | null;
  /** Truncated preview when header auth is used. */
  auth_header_value?: string | null;
  last_response_text?: string | null;
  delivered_at?: string | null;
  failed_at?: string | null;
}

export interface ListWebhookDeliveriesParams {
  status?: string;
  event_type?: string;
  webhook_id?: string;
  skip?: number;
  limit?: number;
}

export interface ListWebhookDeliveriesResponse {
  deliveries: WebhookDelivery[];
  total_count: number;
  skip: number;
}

// Document types
export interface Document {
  id: string;
  pdf_id: string;
  document_name: string;
  upload_date: string;
  uploaded_by: string;
  state: string;
  tag_ids: string[];
  type: string;
  metadata: Record<string, string>;
}

export interface UploadDocument {
  name: string;
  content: string; // Base64 encoded content (supports both plain base64 and data URLs)
  tag_ids?: string[]; // Optional list of tag IDs
  metadata?: Record<string, string>;
}

export interface UploadDocumentsParams {
  documents: UploadDocument[];
}

export interface UploadedDocument {
  document_id: string;
  document_name: string;
  upload_date: string;
  uploaded_by: string;
  state: string;
  tag_ids: string[];
  type?: string;
  metadata: Record<string, string>;
}

export interface UploadDocumentsResponse {
  documents: UploadedDocument[];
}

export interface GetDocumentParams {
  documentId: string;
  fileType: string;
  /** If false, return only metadata (no file content). Default true for backward compatibility. */
  includeContent?: boolean;
}

export interface GetDocumentResponse {
  id: string;
  pdf_id: string;
  document_name: string;
  upload_date: string;
  uploaded_by: string;
  state: string;
  tag_ids: string[];
  type: string | null;
  metadata: Record<string, string>;
  /** Present when includeContent is true (default); null when includeContent is false. */
  content: ArrayBuffer | null;
}

export interface UpdateDocumentParams {
  documentId: string;
  documentName?: string;
  tagIds?: string[];
  metadata?: Record<string, string>;
}

export interface DeleteDocumentParams {
  documentId: string;
}

export interface ListDocumentsParams {
  skip?: number;
  limit?: number;
  tagIds?: string;
  nameSearch?: string;
  metadataSearch?: string;
}

export interface ListDocumentsResponse {
  documents: Document[];
  total_count: number;
  skip: number;
}

// OCR types
export interface OCRGeometry {
  BoundingBox: {
    Width: number;
    Height: number;
    Left: number;
    Top: number;
  };
  Polygon: Array<{ X: number; Y: number }>;
}

export interface OCRBlock {
  BlockType: 'PAGE' | 'LINE' | 'WORD';
  Confidence: number;
  Text?: string;
  Geometry: OCRGeometry;
  Id: string;
  Relationships?: Array<{
    Type: string;
    Ids: string[];
  }>;
  Page: number;
}

export interface GetOCRBlocksParams {
  documentId: string;
}

export interface GetOCRTextParams {
  documentId: string;
  pageNum?: number;
}

export interface GetOCRMetadataParams {
  documentId: string;
}

export interface GetOCRMetadataResponse {
  n_pages: number;
  ocr_date: string;
  ocr_type: string | null;
}

// LLM types
export interface LLMMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface LLMChatRequest {
  model: string;
  messages: LLMMessage[];
  max_tokens?: number;
  temperature?: number;
  stream?: boolean;
}

export interface LLMChatChoice {
  index: number;
  message: {
    role: "assistant";
    content: string;
  };
  finish_reason: string;
}

export interface LLMChatUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface LLMChatResponse {
  id: string;
  object: "chat.completion";
  created: number;
  model: string;
  choices: LLMChatChoice[];
  usage: LLMChatUsage;
}

export interface LLMChatStreamChunk {
  chunk: string;
  done: boolean;
}

export interface LLMChatStreamError {
  error: string;
}

export interface KBChatRequest {
  model: string;
  messages: LLMMessage[];
  max_tokens?: number;
  temperature?: number;
  stream?: boolean; // If false, returns a single JSON object; if true (default), returns SSE stream
  metadata_filter?: Record<string, unknown>;
  upload_date_from?: string;
  upload_date_to?: string;
  /** If set, persist this turn to the thread after success (must belong to this KB). */
  thread_id?: string;
  /** With thread_id: keep only this many messages before appending (resubmit-from-turn). */
  truncate_thread_to_message_count?: number;
}

/** KB / document chat thread list item (same shape as document agent threads). */
export interface ChatThreadSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatThreadDetail {
  id: string;
  title: string;
  messages: Array<Record<string, unknown>>;
  extraction: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreateChatThreadResponse {
  thread_id: string;
}

export interface KBChatStreamChunk {
  chunk?: string;
  type?: 'tool_call' | 'tool_result';
  tool_name?: string;
  arguments?: any;
  results_count?: number;
  iteration?: number;
  error?: string;
  done: boolean;
}

export interface KBChatStreamError {
  error: string;
  done: boolean;
}

export interface LLMEmbeddingTestRequest {
  model: string;
  input: string;
}

export interface LLMEmbeddingTestResponse {
  model: string;
  dimensions: number;
  embedding: number[];
  usage?: {
    prompt_tokens?: number;
    total_tokens?: number;
  } | null;
}

export interface LLMEmbeddingTestRequest {
  model: string;
  input: string;
}

export interface LLMEmbeddingTestResponse {
  model: string;
  dimensions: number;
  embedding: number[];
  usage?: {
    prompt_tokens?: number;
    total_tokens?: number;
  } | null;
}

export interface ListLLMModelsParams {
  providerName?: string;
  providerEnabled?: boolean;
  llmEnabled?: boolean;
  /** Use chat-agent model list (fallback: all enabled) */
  chatAgentOnly?: boolean;
  /** OCR-capable subset (litellm_models_ocr); use for LLM OCR org settings */
  ocrOnly?: boolean;
}

export interface LLMChatModel {
  litellm_model: string;
  litellm_provider: string;
  max_input_tokens: number;
  max_output_tokens: number;
  input_cost_per_token: number;
  output_cost_per_token: number;
  /** Mongo llm_providers.name */
  provider_name?: string;
  provider_display_name?: string;
}

export interface LLMEmbeddingModel {
  litellm_model: string;
  litellm_provider: string;
  max_input_tokens: number;
  dimensions: number;
  input_cost_per_token: number;
  input_cost_per_token_batches: number;
}

export interface ListLLMModelsResponse {
  chat_models: LLMChatModel[];
  embedding_models: LLMEmbeddingModel[];
}

export interface ListOrgLLMModelsResponse {
  models: string[];
}

export interface LLMProvider {
  name: string;
  display_name: string;
  litellm_provider: string;
  litellm_models_enabled: string[];
  litellm_models_available: string[];
  litellm_models_chat_agent: string[];
  enabled: boolean;
  token: string | null;
  token_created_at: string | null;
}

export interface ListLLMProvidersResponse {
  providers: LLMProvider[];
}

export interface SetLLMProviderConfigRequest {
  litellm_models_enabled: string[] | null;
  litellm_models_chat_agent: string[] | null;
  enabled: boolean | null;
  token: string | null;
}

export interface RunLLMParams {
  documentId: string;
  promptRevId: string;
  force?: boolean;
}

export interface RunLLMResponse {
  result_id: string;
  status: string;
}

export interface GetLLMResultParams {
  documentId: string;
  promptRevId: string;
  fallback?: boolean;
}

export interface GetLLMResultResponse {
  prompt_revid: string;
  prompt_id: string;
  prompt_version: number;
  document_id: string;
  llm_result: Record<string, JsonValue>;
  updated_llm_result: Record<string, JsonValue>;
  is_edited: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  /** Display name for the prompt (e.g. "Document Summary" for default prompt). From API. */
  prompt_display_name?: string;
  /** Sanitized prompt and optional grouped-peer match metadata for this run. */
  run?: {
    prompt?: string;
    match_values?: Record<string, unknown>;
    match_document_ids?: string[];
  };
}

export interface DeleteLLMResultParams {
  documentId: string;
  promptId: string;
}

// User types
export interface User {
  id: string;
  email: string;
  name: string | null;
  role: string;
  email_verified: boolean | null;
  created_at: string;
  updated_at: string;
  has_password: boolean;
  has_seen_tour: boolean;
}

export interface UserCreate {
  email: string;
  name: string;
  password: string;
}

export interface UserUpdate {
  name?: string;
  email?: string;
  password?: string;
  role?: string;
  email_verified?: boolean;
  has_seen_tour?: boolean;
}


export interface ListUsersParams {
  skip?: number;
  limit?: number;
  organization_id?: string;
  user_id?: string;
  search_name?: string;
}

export interface ListUsersResponse {
  users: User[];
  total_count: number;
  skip: number;
}

// Tag types
export interface Tag {
  id: string;
  name: string;
  color: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateTagParams {
  tag: Omit<Tag, 'id' | 'created_at' | 'updated_at'>;
}

export interface ListTagsParams {
  skip?: number;
  limit?: number;
  nameSearch?: string;
}

export interface ListTagsResponse {
  tags: Tag[];
  total_count: number;
  skip: number;
}

export interface UpdateTagParams {
  tagId: string;
  tag: Partial<Omit<Tag, 'id' | 'created_at' | 'updated_at'>>;
}

export interface DeleteTagParams {
  tagId: string;
}

// Payment types
export interface PortalSessionResponse {
  url: string;
}




export interface CreditConfig {
  price_per_credit: number;
  currency: string;
  min_cost: number;
  max_cost: number;
}

export interface CreditUpdateResponse {
  credits_added: number;
  new_balance: number;
}

export interface UsageRangeRequest {
  start_date: string;
  end_date: string;
}

export interface UsageRangeResponse {
  usage: Array<{
    date: string;
    credits_used: number;
  }>;
}

// Form types
export interface FormResponseFormat {
  json_formio?: object | null;
  json_formio_mapping?: Record<string, FieldMapping>;
}

export interface FieldMappingSource {
  promptRevId: string;
  promptName: string;
  schemaFieldPath: string;
  schemaFieldName: string;
  schemaFieldType: string;
}

export interface FieldMapping {
  sources: FieldMappingSource[];
  mappingType: 'direct' | 'concatenated' | 'calculated' | 'conditional';
  concatenationSeparator?: string;
}

export interface Form {
  form_revid: string;
  form_id: string;
  form_version: number;
  name: string;
  response_format: FormResponseFormat;
  created_at: string;
  created_by: string;
  tag_ids?: string[];
}

export interface CreateFormParams {
  organizationId: string;
  name: string;
  response_format: FormResponseFormat;
}

export interface ListFormsParams {
  organizationId: string;
  skip?: number;
  limit?: number;
  tag_ids?: string;
}

export interface ListFormsResponse {
  forms: Form[];
  total_count: number;
  skip: number;
}

export interface GetFormParams {
  organizationId: string;
  formRevId: string;
}

export interface UpdateFormParams {
  organizationId: string;
  formId: string;
  form: Partial<Omit<Form, 'form_revid' | 'form_id' | 'form_version' | 'created_at' | 'created_by'>>;
}

export interface DeleteFormParams {
  organizationId: string;
  formId: string;
}

export interface FormSubmission {
  id: string;
  organization_id: string;
  form_revid: string;
  submission_data: Record<string, unknown>;
  submitted_by?: string;
  created_at: string;
  updated_at: string;
}

export interface SubmitFormParams {
  organizationId: string;
  documentId: string;
  formRevId: string;
  submission_data: Record<string, unknown>;
  submitted_by?: string;
}

export interface GetFormSubmissionParams {
  organizationId: string;
  documentId: string;
  formRevId: string;
}

export interface DeleteFormSubmissionParams {
  organizationId: string;
  documentId: string;
  formRevId: string;
}

// Prompt types
export interface Prompt {
  prompt_revid: string;
  prompt_id: string;
  prompt_version: number;
  name: string;
  content: string;
  schema_id?: string;
  schema_version?: number;
  tag_ids?: string[];
  model?: string;
  kb_id?: string;
  // Grouped peer prompt fields (see docs/plan-prompt-group-by.md)
  peer_match_keys?: string[];
  include?: {
    ocr_text?: boolean;
    metadata_keys?: string[];
    pdf?: boolean;
  };
  created_at: string;
  created_by: string;
}

export interface CreatePromptParams {
  organizationId: string;
  prompt: Omit<Prompt, 'prompt_revid' | 'prompt_id' | 'prompt_version' | 'created_at' | 'created_by'>;
}

export interface ListPromptsParams {
  organizationId: string;
  skip?: number;
  limit?: number;
  document_id?: string;
  tag_ids?: string;
  nameSearch?: string;
}

export interface ListPromptsResponse {
  prompts: Prompt[];
  total_count: number;
  skip: number;
}

export interface GetPromptParams {
  organizationId: string;
  promptRevId: string;
}

export interface UpdatePromptParams {
  organizationId: string;
  promptId: string;
  prompt: Partial<Omit<Prompt, 'prompt_revid' | 'prompt_id' | 'prompt_version' | 'created_at' | 'created_by'>>;
}

export interface DeletePromptParams {
  organizationId: string;
  promptId: string;
}


// Schema types
export interface SchemaProperty {
  type: 'string' | 'integer' | 'number' | 'boolean' | 'array' | 'object';
  description?: string;
  items?: SchemaProperty;  // For array types
  properties?: Record<string, SchemaProperty>;  // For object types
  additionalProperties?: boolean;  // Add this for object types
  required?: string[];  // Add this for object types to specify required properties
}

export interface SchemaResponseFormat {
  type: 'json_schema';
  json_schema: {
    name: string;
    schema: {
      type: 'object';
      properties: Record<string, SchemaProperty>;
      required: string[];
      additionalProperties: boolean;
    };
    strict: boolean;
  };
}

export interface Schema {
  schema_revid: string;
  schema_id: string;
  schema_version: number;
  name: string;
  response_format: SchemaResponseFormat;
  created_at: string;
  created_by: string;
}

export interface SchemaConfig {
  name: string;
  response_format: SchemaResponseFormat;
}

export interface CreateSchemaParams {
  organizationId: string;
  name: string;
  response_format: SchemaResponseFormat;
}

export interface ListSchemasParams {
  organizationId: string;
  skip?: number;
  limit?: number;
  nameSearch?: string;
}

export interface ListSchemasResponse {
  schemas: Schema[];
  total_count: number;
  skip: number;
}

export interface GetSchemaParams {
  organizationId: string;
  schemaRevId: string;
}

export interface UpdateSchemaParams {
  organizationId: string;
  schemaId: string;
  schema: Partial<Omit<Schema, 'schema_revid' | 'schema_id' | 'schema_version' | 'created_at' | 'created_by'>>;
}

export interface DeleteSchemaParams {
  organizationId: string;
  schemaId: string;
}

// Invitation types
export interface InvitationResponse {
  id: string;
  email: string;
  organization_id: string;
  organization_name?: string;
  role: string;
  user_exists?: boolean;
  created_at: string;
  expires_at: string;
}

export interface CreateInvitationRequest {
  email: string;
  organization_id?: string;
  role: string;
}

export interface ListInvitationsParams {
  skip?: number;
  limit?: number;
}

export interface ListInvitationsResponse {
  invitations: InvitationResponse[];
  total_count: number;
  skip: number;
}

export interface AcceptInvitationRequest {
  name: string;
  password: string;
}

// Payment types
export interface PortalSessionResponse {
  payment_portal_url: string;
  stripe_enabled: boolean;
}

export interface SubscriptionPlan {
  plan_id: string;
  name: string;
  base_price: number;
  included_spus: number;
  features: string[];
  currency: string;
  interval: string;
}

export interface SubscriptionResponse {
  plans: SubscriptionPlan[];
  current_plan: string | null;
  subscription_status: string | null;
  cancel_at_period_end: boolean;
  current_period_start: number | null;
  current_period_end: number | null;
  stripe_enabled: boolean;
  stripe_payments_portal_enabled: boolean;
}


export interface UsageData {
  subscription_type: string | null;
  usage_unit: string;
  period_metered_usage: number;
  total_metered_usage: number;
  remaining_included: number;
  purchased_credits: number;
  purchased_credits_used: number;
  purchased_credits_remaining: number;
  granted_credits: number;
  granted_credits_used: number;
  granted_credits_remaining: number;
  period_start: number | null;
  period_end: number | null;
}

export interface UsageResponse {
  usage_source: string;
  data: UsageData;
}

export interface UsageRangeRequest {
  start_date: string;
  end_date: string;
}

export interface UsageDataPoint {
  date: string;
  spus: number;
  operation: string;
  source: string;
}

export interface UsageRangeResponse {
  data_points: UsageDataPoint[];
  total_spus: number;
}

// AWS Config types (GET returns masked keys; POST body expects full keys)
export interface AWSConfig {
  access_key_id: string;
  secret_access_key: string;
  s3_bucket_name: string;
  created_at: string;
}

/** GET: masked JSON prefix (same rules as LLM token display). POST: full service account JSON. */
export interface GCPConfig {
  service_account_json: string;
}

/** GET: ``client_secret`` masked; ``tenant_id``, ``client_id``, ``api_base`` returned in full. POST: all fields required in full. */
export interface AzureServicePrincipalConfig {
  tenant_id: string;
  client_id: string;
  client_secret: string;
  /** Foundry / Azure AI base URL (LiteLLM ``api_base``). Stored plaintext in DB. */
  api_base: string;
}

// Knowledge Base types
export type ChunkerType = "token" | "word" | "sentence" | "recursive";
export type KBStatus = "indexing" | "active" | "error";

export type ChunkingPreset = "plain" | "structured_doc";

export interface ChunkingPreprocessConfig {
  prefer_markdown: boolean;
  strip_page_numbers: boolean;
  strip_page_breaks: boolean;
  strip_patterns: string[];
  heading_split_depth: number;
  prepend_heading_path: boolean;
}

/** Baseline preprocessing for a named preset (matches server `chunking_preprocess_for_preset`). */
export function chunkingPreprocessForPreset(preset: ChunkingPreset): ChunkingPreprocessConfig {
  if (preset === "plain") {
    return {
      prefer_markdown: false,
      strip_page_numbers: false,
      strip_page_breaks: false,
      strip_patterns: [],
      heading_split_depth: 3,
      prepend_heading_path: false,
    };
  }
  return {
    prefer_markdown: true,
    strip_page_numbers: true,
    strip_page_breaks: true,
    strip_patterns: [],
    heading_split_depth: 3,
    prepend_heading_path: true,
  };
}

export interface KnowledgeBaseConfig {
  name: string;
  description?: string;
  /** Optional system prompt prepended to prompts that use this KB */
  system_prompt?: string;
  tag_ids?: string[];
  chunker_type?: ChunkerType;
  chunk_size?: number;
  chunk_overlap?: number;
  embedding_model?: string;
  coalesce_neighbors?: number;
  reconcile_enabled?: boolean;
  reconcile_interval_seconds?: number;
  /** Minimum cosine similarity when search falls back to vector-only (empty query or fusion unavailable) */
  min_vector_score?: number | null;
  chunking_preset?: ChunkingPreset | null;
  chunking_preprocess?: ChunkingPreprocessConfig;
}

export interface KnowledgeBaseUpdate {
  name?: string;
  description?: string;
  system_prompt?: string;
  tag_ids?: string[];
  coalesce_neighbors?: number;
  reconcile_enabled?: boolean;
  reconcile_interval_seconds?: number;
  min_vector_score?: number | null;
  chunking_preset?: ChunkingPreset | null;
  chunking_preprocess?: ChunkingPreprocessConfig;
  chunker_type?: ChunkerType;
  chunk_size?: number;
  chunk_overlap?: number;
}

export interface KnowledgeBase extends KnowledgeBaseConfig {
  kb_id: string;
  embedding_dimensions: number;
  status: KBStatus;
  document_count: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
  last_reconciled_at?: string;
}

export interface ListKnowledgeBasesParams {
  skip?: number;
  limit?: number;
  name_search?: string;
}

export interface ListKnowledgeBasesResponse {
  knowledge_bases: KnowledgeBase[];
  total_count: number;
}

export interface GetKnowledgeBaseParams {
  kbId: string;
}

export interface CreateKnowledgeBaseParams {
  organizationId: string;
  kb: KnowledgeBaseConfig;
}

export interface UpdateKnowledgeBaseParams {
  kbId: string;
  update: KnowledgeBaseUpdate;
}

export interface DeleteKnowledgeBaseParams {
  kbId: string;
}

export interface KnowledgeBaseDocument {
  document_id: string;
  document_name: string;
  chunk_count: number;
  indexed_at: string;
}

export interface ListKBDocumentsParams {
  kbId: string;
  skip?: number;
  limit?: number;
}

export interface ListKBDocumentsResponse {
  documents: KnowledgeBaseDocument[];
  total_count: number;
}

export interface KBChunk {
  chunk_index: number;
  chunk_text: string;
  token_count: number;
  indexed_at: string;
  /** UTF-8 character offsets into the canonical indexed full text used at chunking */
  indexed_text_start?: number | null;
  indexed_text_end?: number | null;
  heading_path?: string | null;
  page_start?: number | null;
  page_end?: number | null;
  chunk_type?: string | null;
}

export interface ListKBDocumentChunksParams {
  kbId: string;
  documentId: string;
  skip?: number;
  limit?: number;
}

export interface ListKBChunksResponse {
  chunks: KBChunk[];
  total_count: number;
}

export interface KBSearchRequest {
  query: string;
  top_k?: number;
  skip?: number;
  metadata_filter?: Record<string, unknown>;
  upload_date_from?: string;
  upload_date_to?: string;
  coalesce_neighbors?: number;
}

export interface KBSearchResult {
  content: string;
  source: string;
  document_id: string;
  /** Fused relevance (RRF) from hybrid search, or vector score on vector-only fallback */
  relevance?: number | null;
  chunk_index: number;
  is_matched: boolean;
  /** Present when the vector document stores indexed-text spans (for overlap-safe merging) */
  indexed_text_start?: number | null;
  indexed_text_end?: number | null;
  heading_path?: string | null;
  page_start?: number | null;
  page_end?: number | null;
  chunk_type?: string | null;
}

export interface KBSearchResponse {
  results: KBSearchResult[];
  query: string;
  total_count: number;
  skip: number;
  top_k: number;
}

export interface SearchKnowledgeBaseParams {
  kbId: string;
  search: KBSearchRequest;
}

export interface ReconcileKnowledgeBaseParams {
  kbId: string;
  dry_run?: boolean;
}

export interface ReconcileKnowledgeBaseResponse {
  kb_id: string;
  missing_documents: string[];
  stale_documents: string[];
  orphaned_vectors: number;
  missing_embeddings: number;
  dry_run: boolean;
}

export interface ReconcileAllKnowledgeBasesParams {
  dry_run?: boolean;
}

export interface ReconcileAllKnowledgeBasesResponse {
  kb_results: ReconcileKnowledgeBaseResponse[];
  total_missing: number;
  total_stale: number;
  total_orphaned: number;
  dry_run: boolean;
}
