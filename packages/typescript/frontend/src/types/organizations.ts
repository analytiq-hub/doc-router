export interface OrganizationMember {
  user_id: string;
  role: 'admin' | 'user';
}

export type OrganizationType = 'individual' | 'team' | 'enterprise';

/** Textract is always used; only feature types are configurable. */
export interface OrgOcrTextractSettings {
  feature_types: string[];
}

/** AWS Textract only. */
export interface OrgOcrConfig {
  textract: OrgOcrTextractSettings;
}

export interface OrganizationOcrCatalog {
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