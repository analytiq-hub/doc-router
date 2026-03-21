export interface OrganizationMember {
  user_id: string;
  role: 'admin' | 'user';
}

export type OrganizationType = 'individual' | 'team' | 'enterprise';

export interface OrgOcrTextractSettings {
  enabled: boolean;
  feature_types: string[];
}

export interface OrgOcrGeminiSettings {
  enabled: boolean;
  model: string;
}

export interface OrgOcrVertexSettings {
  enabled: boolean;
  model: string;
}

/**
 * Multiple engines may be enabled; the worker runs implemented backends in order
 * and persists the last successful result.
 */
export interface OrgOcrConfig {
  textract: OrgOcrTextractSettings;
  gemini: OrgOcrGeminiSettings;
  vertex_ai: OrgOcrVertexSettings;
}

export interface OrganizationOcrCatalog {
  gemini_models_available: string[];
  vertex_models_available: string[];
  textract_feature_types: string[];
}

export interface Organization {
  id: string;
  name: string;
  type: OrganizationType;
  members: OrganizationMember[];
  /** When true or undefined, the default prompt is enabled for this organization. */
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