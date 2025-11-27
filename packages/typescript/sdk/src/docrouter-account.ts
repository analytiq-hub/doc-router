import { HttpClient } from './http-client';
import {
  DocRouterAccountConfig,
  AccessToken,
  ListOrganizationsResponse,
  Organization,
  CreateOrganizationRequest,
  UpdateOrganizationRequest,
  CreateTokenRequest,
  ListAccessTokensResponse,
  TokenOrganizationResponse,
  ListLLMModelsParams,
  ListLLMModelsResponse,
  ListLLMProvidersResponse,
  SetLLMProviderConfigRequest,
  LLMChatRequest,
  LLMChatResponse,
  LLMChatStreamChunk,
  LLMChatStreamError,
  ListUsersParams,
  ListUsersResponse,
  UserCreate,
  UserUpdate,
  User,
  AWSConfig,
  // Invitation types
  InvitationResponse,
  CreateInvitationRequest,
  ListInvitationsParams,
  ListInvitationsResponse,
  AcceptInvitationRequest,
  // Payment types
  PortalSessionResponse,
  SubscriptionResponse,
  UsageResponse,
  CreditConfig,
  CreditUpdateResponse,
  UsageRangeRequest,
  UsageRangeResponse,
} from './types';

/**
 * DocRouterAccount - For account-level operations with account tokens
 * Use this for server-to-server integrations that need full account access
 */
export class DocRouterAccount {
  private http: HttpClient;

  constructor(config: DocRouterAccountConfig) {
    this.http = new HttpClient({
      baseURL: config.baseURL,
      token: config.accountToken,
      timeout: config.timeout,
      retries: config.retries,
      onAuthError: config.onAuthError,
    });
  }

  /**
   * Update the account token
   */
  updateToken(token: string): void {
    this.http.updateToken(token);
  }

  // --------------- Organizations ---------------
  async listOrganizations(params?: { 
    userId?: string;
    organizationId?: string;
    nameSearch?: string;
    memberSearch?: string;
    skip?: number;
    limit?: number;
  }): Promise<ListOrganizationsResponse> {
    const queryParams = new URLSearchParams();
    if (params?.userId) queryParams.append('user_id', params.userId);
    if (params?.organizationId) queryParams.append('organization_id', params.organizationId);
    if (params?.nameSearch) queryParams.append('name_search', params.nameSearch);
    if (params?.memberSearch) queryParams.append('member_search', params.memberSearch);
    if (params?.skip !== undefined) queryParams.append('skip', String(params.skip));
    if (params?.limit !== undefined) queryParams.append('limit', String(params.limit));
    return this.http.get<ListOrganizationsResponse>(`/v0/account/organizations?${queryParams.toString()}`);
  }

  async getOrganization(organizationId: string): Promise<Organization> {
    const response = await this.listOrganizations({ organizationId });
    return response.organizations[0];
  }

  async createOrganization(organization: CreateOrganizationRequest): Promise<Organization> {
    const response = await this.http.post<{
      _id?: string;
      id: string;
      name: string;
      members: Organization['members'];
      type: Organization['type'];
      created_at: string;
      updated_at: string;
    }>(`/v0/account/organizations`, organization);
    return {
      id: response._id || response.id,
      name: response.name,
      members: response.members,
      type: response.type,
      created_at: response.created_at,
      updated_at: response.updated_at,
    };
  }

  async updateOrganization(organizationId: string, update: UpdateOrganizationRequest): Promise<Organization> {
    return this.http.put(`/v0/account/organizations/${organizationId}`, update);
  }

  async deleteOrganization(organizationId: string) {
    return this.http.delete(`/v0/account/organizations/${organizationId}`);
  }

  // --------------- Tokens ---------------
  async createAccountToken(request: CreateTokenRequest): Promise<AccessToken> {
    return this.http.post(`/v0/account/access_tokens`, request);
  }

  async getAccountTokens(): Promise<AccessToken[]> {
    const resp = await this.http.get<ListAccessTokensResponse | AccessToken[]>(`/v0/account/access_tokens`);
    // Normalize to array for SDK consumers/tests
    return Array.isArray(resp) ? resp : (resp as ListAccessTokensResponse).access_tokens;
  }

  async deleteAccountToken(tokenId: string): Promise<void> {
    return this.http.delete(`/v0/account/access_tokens/${tokenId}`);
  }

  async createOrganizationToken(request: CreateTokenRequest, organizationId: string): Promise<AccessToken> {
    return this.http.post(`/v0/orgs/${organizationId}/access_tokens`, request);
  }

  async getOrganizationTokens(organizationId: string): Promise<AccessToken[]> {
    const resp = await this.http.get<ListAccessTokensResponse | AccessToken[]>(`/v0/orgs/${organizationId}/access_tokens`);
    // Normalize to array for SDK consumers/tests
    return Array.isArray(resp) ? resp : (resp as ListAccessTokensResponse).access_tokens;
  }

  async deleteOrganizationToken(tokenId: string, organizationId: string): Promise<void> {
    return this.http.delete(`/v0/orgs/${organizationId}/access_tokens/${tokenId}`);
  }

  /**
   * Get the organization ID associated with an API token
   * @param token The API token to resolve
   * @returns The organization ID for org-specific tokens, or null for account-level tokens
   */
  async getOrganizationFromToken(token: string): Promise<TokenOrganizationResponse> {
    return this.http.get<TokenOrganizationResponse>(`/v0/account/token/organization?token=${encodeURIComponent(token)}`);
  }

  // --------------- LLM (account-level) ---------------
  async listLLMModels(params: ListLLMModelsParams): Promise<ListLLMModelsResponse> {
    return this.http.get<ListLLMModelsResponse>('/v0/account/llm/models', {
      params: {
        provider_name: params.providerName,
        provider_enabled: params.providerEnabled,
        llm_enabled: params.llmEnabled,
      }
    });
  }

  async listLLMProviders(): Promise<ListLLMProvidersResponse> {
    return this.http.get<ListLLMProvidersResponse>('/v0/account/llm/providers');
  }

  async setLLMProviderConfig(providerName: string, request: SetLLMProviderConfigRequest) {
    return this.http.put<SetLLMProviderConfigRequest>(`/v0/account/llm/provider/${providerName}`, request);
  }

  // --------------- Users ---------------
  async listUsers(params?: ListUsersParams): Promise<ListUsersResponse> {
    const queryParams = new URLSearchParams();
    if (params?.skip) queryParams.append('skip', String(params.skip));
    if (params?.limit) queryParams.append('limit', String(params.limit));
    if (params?.organization_id) queryParams.append('organization_id', params.organization_id);
    if (params?.user_id) queryParams.append('user_id', params.user_id);
    if (params?.search_name) queryParams.append('search_name', params.search_name);
    return this.http.get<ListUsersResponse>(`/v0/account/users?${queryParams.toString()}`);
  }

  async getUser(userId: string): Promise<User> {
    const response = await this.listUsers({ user_id: userId });
    return response.users[0];
  }

  async createUser(user: UserCreate): Promise<User> {
    return this.http.post<User>('/v0/account/users', user);
  }

  async updateUser(userId: string, update: UserUpdate): Promise<User> {
    return this.http.put<User>(`/v0/account/users/${userId}`, update);
  }

  async deleteUser(userId: string): Promise<void> {
    await this.http.delete(`/v0/account/users/${userId}`);
  }

  // --------------- Email Verification ---------------
  async sendVerificationEmail(userId: string) {
    return this.http.post(`/v0/account/email/verification/send/${userId}`);
  }

  async sendRegistrationVerificationEmail(userId: string) {
    return this.http.post(`/v0/account/email/verification/register/${userId}`);
  }

  async verifyEmail(token: string) {
    return this.http.post(`/v0/account/email/verification/${token}`);
  }

  // --------------- AWS Config ---------------
  async createAWSConfig(config: Omit<AWSConfig, 'created_at'>): Promise<AWSConfig> {
    return this.http.post('/v0/account/aws_config', config);
  }

  async getAWSConfig(): Promise<AWSConfig> {
    return this.http.get('/v0/account/aws_config');
  }

  async deleteAWSConfig(): Promise<void> {
    return this.http.delete('/v0/account/aws_config');
  }

  // --------------- Invitations ---------------
  async createInvitation(invitation: CreateInvitationRequest): Promise<InvitationResponse> {
    return this.http.post<InvitationResponse>('/v0/account/email/invitations', invitation);
  }

  async getInvitations(params?: ListInvitationsParams): Promise<ListInvitationsResponse> {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', String(params.skip));
    if (params?.limit !== undefined) queryParams.append('limit', String(params.limit));
    return this.http.get<ListInvitationsResponse>(`/v0/account/email/invitations?${queryParams.toString()}`);
  }

  async getInvitation(token: string): Promise<InvitationResponse> {
    return this.http.get<InvitationResponse>(`/v0/account/email/invitations/${token}`);
  }

  async acceptInvitation(token: string, data: AcceptInvitationRequest): Promise<{ message: string }> {
    return this.http.post<{ message: string }>(`/v0/account/email/invitations/${token}/accept`, data);
  }

  // --------------- Payments & Subscriptions ---------------
  async getCustomerPortal(orgId: string): Promise<PortalSessionResponse> {
    return this.http.post<PortalSessionResponse>(`/v0/orgs/${orgId}/payments/customer-portal`);
  }

  async getSubscription(orgId: string): Promise<SubscriptionResponse> {
    return this.http.get<SubscriptionResponse>(`/v0/orgs/${orgId}/payments/subscription`);
  }

  async activateSubscription(orgId: string): Promise<{ status: string; message: string }> {
    return this.http.put<{ status: string; message: string }>(`/v0/orgs/${orgId}/payments/subscription`);
  }

  async cancelSubscription(orgId: string): Promise<{ status: string; message: string }> {
    return this.http.delete<{ status: string; message: string }>(`/v0/orgs/${orgId}/payments/subscription`);
  }

  async getCurrentUsage(orgId: string): Promise<UsageResponse> {
    return this.http.get<UsageResponse>(`/v0/orgs/${orgId}/payments/usage`);
  }

  async addCredits(orgId: string, amount: number): Promise<CreditUpdateResponse> {
    return this.http.post<CreditUpdateResponse>(`/v0/orgs/${orgId}/payments/credits/add`, { amount });
  }

  async getCreditConfig(orgId: string): Promise<CreditConfig> {
    return this.http.get<CreditConfig>(`/v0/orgs/${orgId}/payments/credits/config`);
  }

  async purchaseCredits(orgId: string, request: { credits: number; success_url: string; cancel_url: string }): Promise<{ checkout_url: string; session_id: string }> {
    return this.http.post<{ checkout_url: string; session_id: string }>(`/v0/orgs/${orgId}/payments/credits/purchase`, request);
  }

  async getUsageRange(orgId: string, request: UsageRangeRequest): Promise<UsageRangeResponse> {
    const queryParams = new URLSearchParams();
    if (request.start_date) queryParams.append('start_date', request.start_date);
    if (request.end_date) queryParams.append('end_date', request.end_date);
    return this.http.get<UsageRangeResponse>(`/v0/orgs/${orgId}/payments/usage/range?${queryParams.toString()}`);
  }

  async createCheckoutSession(orgId: string, planId: string): Promise<PortalSessionResponse> {
    return this.http.post<PortalSessionResponse>(`/v0/orgs/${orgId}/payments/checkout-session`, { plan_id: planId });
  }

  /**
   * Run LLM chat (account level)
   */
  async runLLMChat(request: LLMChatRequest): Promise<LLMChatResponse> {
    return this.http.post('/v0/account/llm/run', request);
  }

  /**
   * Run LLM chat with streaming (account level)
   */
  async runLLMChatStream(
    request: LLMChatRequest,
    onChunk: (chunk: LLMChatStreamChunk | LLMChatStreamError) => void,
    onError?: (error: Error) => void,
    abortSignal?: AbortSignal
  ): Promise<void> {
    const streamingRequest = { ...request, stream: true };
    return this.http.stream('/v0/account/llm/run', streamingRequest, onChunk, onError, abortSignal);
  }

  /**
   * Get the current HTTP client (for advanced usage)
   */
  getHttpClient(): HttpClient {
    return this.http;
  }
}
