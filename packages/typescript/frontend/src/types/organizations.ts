export interface OrganizationMember {
  user_id: string;
  role: 'admin' | 'user';
}

export type OrganizationType = 'individual' | 'team' | 'enterprise';

/** Textract AnalyzeDocument feature types (used when `mode` is `textract`). */
export interface OrgOcrTextractSettings {
  feature_types: string[];
}

export type OrgOcrMistralSettings = Record<string, never>;

export type OrgOcrPymupdfSettings = Record<string, never>;

export interface OrgOcrLlmSettings {
  provider: string | null;
  model: string | null;
}

export type OcrMode = 'textract' | 'mistral' | 'llm' | 'pymupdf';

export interface OrgOcrConfig {
  mode: OcrMode;
  textract: OrgOcrTextractSettings;
  mistral: OrgOcrMistralSettings;
  pymupdf: OrgOcrPymupdfSettings;
  llm: OrgOcrLlmSettings;
}

export interface OrganizationOcrCatalog {
  textract_feature_types: string[];
  modes: string[];
  /** False when Mistral provider is off or no models enabled in llm_providers. */
  mistral_enabled?: boolean;
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