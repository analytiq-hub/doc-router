export interface OrganizationMember {
  user_id: string;
  role: 'admin' | 'user';
}

export type OrganizationType = 'individual' | 'team' | 'enterprise';

export interface Organization {
  id: string;
  name: string;
  type: OrganizationType;
  members: OrganizationMember[];
  created_at: string;
  updated_at: string;
  mcp_enabled?: boolean;
}

export interface CreateOrganizationRequest {
  name: string;
  type?: OrganizationType;
  mcp_enabled?: boolean;
}

export interface UpdateOrganizationRequest {
  name?: string;
  type?: OrganizationType;
  members?: OrganizationMember[];
  mcp_enabled?: boolean;
}

export interface ListOrganizationsResponse {
  organizations: Organization[];
}