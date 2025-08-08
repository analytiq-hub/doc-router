import axios, { isAxiosError } from 'axios';
import { getSession } from 'next-auth/react';
import { AppSession } from '@/types/AppSession';

// Session cache to avoid repeated calls
let sessionCache: { session: AppSession | null; timestamp: number } | null = null;
const SESSION_CACHE_DURATION = 30000; // 30 seconds

// Global session reference for context-based access
let globalSession: AppSession | null = null;

export function setGlobalSession(session: AppSession | null): void {
  globalSession = session;
}

export function getGlobalSession(): AppSession | null {
  return globalSession;
}

export async function getCachedSession(): Promise<AppSession | null> {
  // First try to use global session from context
  if (globalSession) {
    return globalSession;
  }
  
  const now = Date.now();
  
  if (sessionCache && (now - sessionCache.timestamp) < SESSION_CACHE_DURATION) {
    return sessionCache.session;
  }
  
  const session = await getSession() as AppSession | null;
  sessionCache = { session, timestamp: now };
  return session;
}

// Function to invalidate session cache
export function invalidateSessionCache(): void {
  sessionCache = null;
  globalSession = null;
}
import { 
  UploadDocumentsParams,
  UploadDocumentsResponse,
  GetDocumentParams,
  GetDocumentResponse,
  UpdateDocumentParams,
  DeleteDocumentParams,
  ListDocumentsParams,
} from '@/types/index';
import {
  GetOCRBlocksParams,
  GetOCRTextParams,
  GetOCRMetadataParams,
  GetOCRMetadataResponse
} from '@/types/index';
import { 
  UserCreate, 
  UserUpdate, 
  UserResponse, 
  ListUsersParams, 
  ListUsersResponse 
} from '@/types/index';
import { 
  CreateOrganizationRequest, 
  ListOrganizationsResponse, 
  Organization, 
  UpdateOrganizationRequest 
} from '@/types/index';
import { 
  Schema, 
  CreateSchemaParams,
  ListSchemasParams,
  ListSchemasResponse,
  GetSchemaParams,
  UpdateSchemaParams,
  DeleteSchemaParams,
} from '@/types/index';
import { 
  InvitationResponse, 
  CreateInvitationRequest, 
  ListInvitationsParams, 
  ListInvitationsResponse, 
  AcceptInvitationRequest 
} from '@/types/index';
import { CreateTokenRequest } from '@/types/index';
import { AWSCredentials } from '@/types/index';
import {
  ListLLMModelsParams,
  ListLLMModelsResponse,
  ListLLMProvidersResponse,
  SetLLMProviderConfigRequest,
  RunLLMParams,
  RunLLMResponse, 
  GetLLMResultParams,
  GetLLMResultResponse,
  DeleteLLMResultParams,
} from '@/types/index';
import { 
  Prompt,
  CreatePromptParams,
  ListPromptsResponse, 
  ListPromptsParams,
  GetPromptParams,
  UpdatePromptParams,
  DeletePromptParams,
} from '@/types/index';
import { 
  Tag, 
  ListTagsResponse,
  CreateTagParams,
  ListTagsParams,
  UpdateTagParams,
  DeleteTagParams,
} from '@/types/index';
import { 
  Flow, 
  ListFlowsResponse,
  CreateFlowParams,
  UpdateFlowParams,
  ListFlowsParams,
  GetFlowParams,
  DeleteFlowParams,
} from '@/types/index';
import { 
  PortalSessionResponse,
  SubscriptionResponse,
  UsageResponse,
  CreditConfig,
  CreditUpdateResponse,
} from '@/types/index';
import { toast } from 'react-toastify';
import { JsonValue } from 'type-fest';
import {
  CreateFormParams,
  Form,
  ListFormsParams,
  ListFormsResponse,
  GetFormParams,
  UpdateFormParams,
  DeleteFormParams,
  SubmitFormParams,
  GetFormSubmissionParams,
  FormSubmission,
  DeleteFormSubmissionParams
} from '@/types/forms';
import {
  CreateTableParams,
  Table,
  ListTablesParams,
  ListTablesResponse,
  GetTableParams,
  UpdateTableParams,
  DeleteTableParams,
  SubmitTableParams as SubmitTableParamsTable,
  GetTableSubmissionParams,
  TableSubmission,
  DeleteTableSubmissionParams
} from '@/types/tables';

// These APIs execute from the frontend
const NEXT_PUBLIC_FASTAPI_FRONTEND_URL = process.env.NEXT_PUBLIC_FASTAPI_FRONTEND_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: NEXT_PUBLIC_FASTAPI_FRONTEND_URL, 
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Add authorization header to all requests
api.interceptors.request.use(async (config) => {
  // First try to use global session (pre-fetched from context)
  let session = getGlobalSession();
  
  // Fallback to cached session if global session is not available
  if (!session) {
    session = await getCachedSession();
  }
  
  if (session?.apiAccessToken) {
    config.headers.Authorization = `Bearer ${session.apiAccessToken}`;
  } else {
    console.warn('No API token found in session');
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Add a request queue to handle concurrent requests during token refresh
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (error: Error) => void;
}> = [];

const processQueue = (error: Error | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve();
    }
  });
  failedQueue = [];
};

// Store the toast ID outside the interceptor
let sessionExpiredToastId: React.ReactText | null = null;

// Add a response interceptor that handles all errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Handle 401 errors (unauthorized)
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => api(originalRequest))
          .catch(() => {
            // Only show session expiration toast once
            if (!sessionExpiredToastId || !toast.isActive(sessionExpiredToastId)) {
              sessionExpiredToastId = toast.error('Your session has expired. Please login again.');
            }
            return Promise.reject(new Error('Session expired'));
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Invalidate cache and get fresh session on 401
        invalidateSessionCache();
        const session = await getCachedSession();
        if (session?.apiAccessToken) {
          originalRequest.headers.Authorization = `Bearer ${session.apiAccessToken}`;
          processQueue();
          return api(originalRequest);
        } else {
          if (!sessionExpiredToastId || !toast.isActive(sessionExpiredToastId)) {
            sessionExpiredToastId = toast.error('Your session has expired. Please login again.');
          }
          return Promise.reject(new Error('Session expired'));
        }
      } catch (refreshError) {
        processQueue(refreshError instanceof Error ? refreshError : new Error('Token refresh failed'));
        if (!sessionExpiredToastId || !toast.isActive(sessionExpiredToastId)) {
          sessionExpiredToastId = toast.error('Your session has expired. Please login again.');
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // For all other errors, just pass through the error without showing toast
    if (isAxiosError(error)) {
      const responseData = error.response?.data as { detail?: string };
      if (responseData?.detail) {
        return Promise.reject(new Error(responseData.detail));
      }
    }

    return Promise.reject(error);
  }
);

// Document APIs
export const uploadDocumentsApi = async (params: UploadDocumentsParams): Promise<UploadDocumentsResponse> => {
  const { organizationId, documents } = params;
  const response = await api.post<UploadDocumentsResponse>(`/v0/orgs/${organizationId}/documents`, { documents: documents });
  return response.data;
};

export const listDocumentsApi = async (params?: ListDocumentsParams) => {
  const queryParams: Record<string, string | number | undefined> = {
    skip: params?.skip || 0,
    limit: params?.limit || 10,
  };
  
  if (params?.tagIds) {
    queryParams.tag_ids = params.tagIds;
  }
  
  if (params?.nameSearch) {
    queryParams.name_search = params.nameSearch;
  }
  
  const response = await api.get(`/v0/orgs/${params?.organizationId}/documents`, { 
    params: queryParams
  });
  return response.data;
};

export const getDocumentApi = async (params: GetDocumentParams): Promise<GetDocumentResponse> => {
  const { organizationId, documentId, fileType } = params;
  // Always request the associated PDF
  const response = await api.get(`/v0/orgs/${organizationId}/documents/${documentId}?file_type=${fileType}`);
  const data = response.data;
  
  // Convert base64 content back to ArrayBuffer
  const binaryContent = atob(data.content);
  const len = binaryContent.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryContent.charCodeAt(i);
  }

  return {
    metadata: data.metadata,
    content: bytes.buffer
  };
};

export const updateDocumentApi = async (params: UpdateDocumentParams) => {
  const { organizationId, documentId, documentName, tagIds } = params;
  const updateData: { tag_ids?: string[]; document_name?: string } = {};
  
  if (documentName !== undefined) {
    updateData.document_name = documentName;
  }

  if (tagIds) {
    updateData.tag_ids = tagIds;
  }
  
  const response = await api.put(`/v0/orgs/${organizationId}/documents/${documentId}`, updateData);
  return response.data;
};

export const deleteDocumentApi = async (params: DeleteDocumentParams) => {
  const { organizationId, documentId } = params;
  const response = await api.delete(`/v0/orgs/${organizationId}/documents/${documentId}`);
  return response.data;
};

// OCR APIs
export const getOCRBlocksApi = async (params: GetOCRBlocksParams) => {
  const { organizationId, documentId } = params;
  const response = await api.get(`/v0/orgs/${organizationId}/ocr/download/blocks/${documentId}`);
  return response.data;
};

export const getOCRTextApi = async (params: GetOCRTextParams) => {
  const { organizationId, documentId, pageNum } = params;
  const url = `/v0/orgs/${organizationId}/ocr/download/text/${documentId}${pageNum ? `?page_num=${pageNum}` : ''}`;
  const response = await api.get(url);
  return response.data;
};

export const getOCRMetadataApi = async (params: GetOCRMetadataParams) => {
  const { organizationId, documentId } = params;
  const response = await api.get<GetOCRMetadataResponse>(`/v0/orgs/${organizationId}/ocr/download/metadata/${documentId}`);
  return response.data;
};

// LLM APIs
export const listLLMModelsApi = async (params: ListLLMModelsParams): Promise<ListLLMModelsResponse> => {
  const response = await api.get<ListLLMModelsResponse>('/v0/account/llm_models', {
    params: {
      provider_name: params.providerName,
      provider_enabled: params.providerEnabled,
      llm_enabled: params.llmEnabled,
    }
  });
  return response.data;
};

export const listLLMProvidersApi = async (): Promise<ListLLMProvidersResponse> => {
  const response = await api.get<ListLLMProvidersResponse>('/v0/account/llm_providers');
  return response.data;
};

export const setLLMProviderConfigApi = async (providerName: string, request: SetLLMProviderConfigRequest) => {
  const response = await api.put<SetLLMProviderConfigRequest>(`/v0/account/llm_provider/${providerName}`, request);
  return response.data;
};

export const runLLMApi = async (params: RunLLMParams) => {
  const { organizationId, documentId, promptRevId, force } = params;
  const response = await api.post<RunLLMResponse>(
    `/v0/orgs/${organizationId}/llm/run/${documentId}`,
    {},
    {
      params: {
        prompt_rev_id: promptRevId,
        force: force
      }
    }
  );
  return response.data;
};

export const getLLMResultApi = async (params: GetLLMResultParams) => {
  const { organizationId, documentId, promptRevId, latest } = params;
  const response = await api.get<GetLLMResultResponse>(
    `/v0/orgs/${organizationId}/llm/result/${documentId}`,
    {
      params: {
        prompt_rev_id: promptRevId,
        latest: latest
      }
    }
  );
  return response.data;
};

export const updateLLMResultApi = async ({
  organizationId,
  documentId,
  promptId,
  result,
  isVerified = false
}: {
  organizationId: string;
  documentId: string;
  promptId: string;
  result: Record<string, JsonValue>;
  isVerified?: boolean;
}) => {
  const response = await api.put(
    `/v0/orgs/${organizationId}/llm/result/${documentId}`,
    {
      updated_llm_result: result,
      is_verified: isVerified
    },
    {
      params: {
        prompt_rev_id: promptId
      }
    }
  );

  if (response.status !== 200) {
    throw new Error(`Failed to update LLM result for document ${documentId} and prompt ${promptId}: ${response.data}`);
  }

  return response.data;
};

export const deleteLLMResultApi = async (params: DeleteLLMResultParams) => {
  const { organizationId, documentId, promptId } = params;
  const response = await api.delete(
    `/v0/orgs/${organizationId}/llm/result/${documentId}`,
    {
      params: {
        prompt_rev_id: promptId
      }
    }
  );
  return response.data;
};

// Schema APIs
export const createSchemaApi = async (schema: CreateSchemaParams) => {
  const { organizationId, ...schemaConfig } = schema;
  const response = await api.post<Schema>(`/v0/orgs/${organizationId}/schemas`, schemaConfig);
  return response.data;
};

export const listSchemasApi = async (params: ListSchemasParams): Promise<ListSchemasResponse> => {
  const { organizationId, ...rest } = params;
  const response = await api.get<ListSchemasResponse>(`/v0/orgs/${organizationId}/schemas`, {
    params: {
      skip: rest?.skip || 0,
      limit: rest?.limit || 10
    }
  });
  return response.data;
};

export const getSchemaApi = async (params: GetSchemaParams): Promise<Schema> => {
  const { organizationId, schemaId } = params;
  const response = await api.get<Schema>(`/v0/orgs/${organizationId}/schemas/${schemaId}`);
  return response.data;
};

export const updateSchemaApi = async (params: UpdateSchemaParams): Promise<Schema> => {
  const { organizationId, schemaId, schema } = params;
  const response = await api.put<Schema>(`/v0/orgs/${organizationId}/schemas/${schemaId}`, schema);
  return response.data;
};

export const deleteSchemaApi = async (params: DeleteSchemaParams) => {
  const { organizationId, schemaId } = params;
  const response = await api.delete(`/v0/orgs/${organizationId}/schemas/${schemaId}`);
  return response.data;
};

// Prompt APIs
export const createPromptApi = async (params: CreatePromptParams): Promise<Prompt> => {
  const { organizationId, prompt } = params;
  const response = await api.post<Prompt>(`/v0/orgs/${organizationId}/prompts`, prompt);
  return response.data;
};

export const listPromptsApi = async (params: ListPromptsParams): Promise<ListPromptsResponse> => {
  const { organizationId, ...rest } = params;
  const response = await api.get<ListPromptsResponse>(`/v0/orgs/${organizationId}/prompts`, {
    params: {
      skip: rest?.skip || 0,
      limit: rest?.limit || 10,
      document_id: rest?.document_id,
      tag_ids: rest?.tag_ids
    }
  });
  return response.data;
};

export const getPromptApi = async (params: GetPromptParams): Promise<Prompt> => {
  const { organizationId, promptId } = params;
  const response = await api.get<Prompt>(`/v0/orgs/${organizationId}/prompts/${promptId}`);
  return response.data;
};

export const updatePromptApi = async (params: UpdatePromptParams): Promise<Prompt> => {
  const { organizationId, promptId, prompt } = params;
  const response = await api.put<Prompt>(`/v0/orgs/${organizationId}/prompts/${promptId}`, prompt);
  return response.data;
};

export const deletePromptApi = async (params: DeletePromptParams): Promise<void> => {
  const { organizationId, promptId } = params;
  const response = await api.delete(`/v0/orgs/${organizationId}/prompts/${promptId}`);
  return response.data;
};

// Form APIs
export const createFormApi = async (form: CreateFormParams) => {
  const { organizationId, ...formConfig } = form;
  const response = await api.post<Form>(`/v0/orgs/${organizationId}/forms`, formConfig);
  return response.data;
};

export const listFormsApi = async (params: ListFormsParams): Promise<ListFormsResponse> => {
  const { organizationId, ...rest } = params;
  const response = await api.get<ListFormsResponse>(`/v0/orgs/${organizationId}/forms`, {
    params: {
      skip: rest?.skip || 0,
      limit: rest?.limit || 10,
      tag_ids: rest?.tag_ids // Add tag_ids support
    }
  });
  return response.data;
};

export const getFormApi = async (params: GetFormParams): Promise<Form> => {
  const { organizationId, formRevId } = params;
  const response = await api.get<Form>(`/v0/orgs/${organizationId}/forms/${formRevId}`);
  return response.data;
};

export const updateFormApi = async (params: UpdateFormParams): Promise<Form> => {
  const { organizationId, formId, form } = params;
  const response = await api.put<Form>(`/v0/orgs/${organizationId}/forms/${formId}`, form);
  return response.data;
};

export const deleteFormApi = async (params: DeleteFormParams) => {
  const { organizationId, formId } = params;
  const response = await api.delete(`/v0/orgs/${organizationId}/forms/${formId}`);
  return response.data;
};

export const submitFormApi = async (params: SubmitFormParams): Promise<FormSubmission> => {
  const { organizationId, documentId, submission } = params;
  
  const response = await api.post<FormSubmission>(
    `/v0/orgs/${organizationId}/forms/submissions/${documentId}`, 
    submission
  );
  return response.data;
};

export const getFormSubmissionApi = async (params: GetFormSubmissionParams): Promise<FormSubmission | null> => {
  const { organizationId, documentId, formRevId } = params;
  const response = await api.get<FormSubmission | null>(
    `/v0/orgs/${organizationId}/forms/submissions/${documentId}?form_revid=${formRevId}`
  );
  return response.data;
};

export const deleteFormSubmissionApi = async (params: DeleteFormSubmissionParams): Promise<void> => {
  const { organizationId, documentId, formRevId } = params;
  const response = await api.delete(`/v0/orgs/${organizationId}/forms/submissions/${documentId}`, {
    params: {
      form_revid: formRevId
    }
  });
  return response.data;
};


// Tag APIs
export const createTagApi = async (params: CreateTagParams): Promise<Tag> => {
    const { organizationId, tag } = params;
    const response = await api.post<Tag>(`/v0/orgs/${organizationId}/tags`, tag);
    return response.data;
};

export const getTagApi = async ({
  organizationId,
  tagId,
}: {
  organizationId: string;
  tagId: string;
}): Promise<Tag> => {
  const response = await api.get<Tag>(`/v0/orgs/${organizationId}/tags/${tagId}`);
  return response.data;
};

export const listTagsApi = async (params: ListTagsParams): Promise<ListTagsResponse> => {
    const { organizationId } = params;
    const response = await api.get<ListTagsResponse>(`/v0/orgs/${organizationId}/tags`);
    return response.data;
};

export const updateTagApi = async (params: UpdateTagParams): Promise<Tag> => {
    const { organizationId, tagId, tag } = params;
    const response = await api.put<Tag>(`/v0/orgs/${organizationId}/tags/${tagId}`, tag);
    return response.data;
};

export const deleteTagApi = async (params: DeleteTagParams): Promise<void> => {
  const { organizationId, tagId } = params;
  await api.delete(`/v0/orgs/${organizationId}/tags/${tagId}`);
};

// Flow APIs
export const createFlowApi = async (params: CreateFlowParams): Promise<Flow> => {
  const { organizationId, flow } = params;
  const response = await api.post<Flow>(`/v0/orgs/${organizationId}/flows`, flow);
  return response.data;
};

export const updateFlowApi = async (params: UpdateFlowParams): Promise<Flow> => {
  const { organizationId, flowId, flow } = params;
  const response = await api.put<Flow>(`/v0/orgs/${organizationId}/flows/${flowId}`, flow);
  return response.data;
};

export const listFlowsApi = async (params: ListFlowsParams): Promise<ListFlowsResponse> => {
  const { organizationId, ...rest } = params;
  const response = await api.get<ListFlowsResponse>(`/v0/orgs/${organizationId}/flows`, {
    params: {
      skip: rest?.skip || 0,
      limit: rest?.limit || 10
    }
  });
  return response.data;
};

export const getFlowApi = async (params: GetFlowParams): Promise<Flow> => {
  const { organizationId, flowId } = params;
  const response = await api.get<Flow>(`/v0/orgs/${organizationId}/flows/${flowId}`);
  return response.data;
};

export const deleteFlowApi = async (params: DeleteFlowParams): Promise<void> => {
  const { organizationId, flowId } = params;
  await api.delete(`/v0/orgs/${organizationId}/flows/${flowId}`);
};

// Account Token APIs
export const createAccountTokenApi = async (token: CreateTokenRequest) => {
  const response = await api.post('/v0/account/access_tokens', token);
  return response.data;
};

export const getAccountTokensApi = async () => {
  const response = await api.get('/v0/account/access_tokens');
  return response.data;
};

export const deleteAccountTokenApi = async (tokenId: string) => {
  const response = await api.delete(`/v0/account/access_tokens/${tokenId}`);
  return response.data;
};

// Organization Token APIs
export const createOrganizationTokenApi = async (token: CreateTokenRequest, organizationId: string) => {
  const endpoint = `/v0/orgs/${organizationId}/access_tokens`;
  const response = await api.post(endpoint, token);
  return response.data;
};

export const getOrganizationTokensApi = async (organizationId: string) => {
  const endpoint = `/v0/orgs/${organizationId}/access_tokens`;
  const response = await api.get(endpoint);
  return response.data;
};

export const deleteOrganizationTokenApi = async (tokenId: string, organizationId: string) => {
  const endpoint = `/v0/orgs/${organizationId}/access_tokens/${tokenId}`;
  const response = await api.delete(endpoint);
  return response.data;
};

// AWS APIs
export const createAWSCredentialsApi = async (credentials: Omit<AWSCredentials, 'created_at'>) => {
  const response = await api.post('/v0/account/aws_credentials', credentials);
  return response.data;
};

export const getAWSCredentialsApi = async () => {
  const response = await api.get('/v0/account/aws_credentials');
  return response.data;
};

export const deleteAWSCredentialsApi = async () => {
  const response = await api.delete('/v0/account/aws_credentials');
  return response.data;
};

// Organization APIs
export const getOrganizationsApi = async (params?: { 
  userId?: string;
  organizationId?: string;
}): Promise<ListOrganizationsResponse> => {
  const queryParams = new URLSearchParams();
  if (params?.userId) queryParams.append('user_id', params.userId);
  if (params?.organizationId) queryParams.append('organization_id', params.organizationId);
  
  const response = await api.get<ListOrganizationsResponse>(
    `/v0/account/organizations?${queryParams.toString()}`
  );
  return response.data;
};

export const createOrganizationApi = async (organization: CreateOrganizationRequest): Promise<Organization> => {
  const response = await api.post('/v0/account/organizations', organization);
  const data = response.data;
  return {
    id: data._id || data.id,
    name: data.name,
    members: data.members,
    type: data.type,
    created_at: data.created_at,
    updated_at: data.updated_at
  };
};

export const getOrganizationApi = async (organizationId: string): Promise<Organization> => {
  const response = await getOrganizationsApi({ organizationId });
  return response.organizations[0]; // Will always return exactly one organization
};

export const updateOrganizationApi = async (
  organizationId: string, 
  update: UpdateOrganizationRequest
): Promise<Organization> => {
  const response = await api.put(`/v0/account/organizations/${organizationId}`, update);
  return response.data;
};

export const deleteOrganizationApi = async (organizationId: string) => {
  const response = await api.delete(`/v0/account/organizations/${organizationId}`);
  return response.data;
};

// User APIs

export const getUsersApi = async (params?: ListUsersParams): Promise<ListUsersResponse> => {
  const queryParams = new URLSearchParams();
  if (params?.skip) queryParams.append('skip', params.skip.toString());
  if (params?.limit) queryParams.append('limit', params.limit.toString());
  if (params?.organization_id) queryParams.append('organization_id', params.organization_id);
  if (params?.user_id) queryParams.append('user_id', params.user_id);

  const response = await api.get<ListUsersResponse>(
    `/v0/account/users?${queryParams.toString()}`
  );
  return response.data;
};

export const createUserApi = async (user: UserCreate): Promise<UserResponse> => {
  const response = await api.post('/v0/account/users', user);
  return response.data;
};

export const deleteUserApi = async (userId: string): Promise<void> => {
  await api.delete(`/v0/account/users/${userId}`);
};

export const getUserApi = async (userId: string): Promise<UserResponse> => {
  const response = await getUsersApi({ user_id: userId });
  return response.users[0]; // Will always return exactly one user
};

export const updateUserApi = async (userId: string, update: UserUpdate): Promise<UserResponse> => {
  const response = await api.put<UserResponse>(`/v0/account/users/${userId}`, update);
  return response.data;
};

export function getApiErrorMsg(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  
  if (isAxiosError(error)) {
    const responseData = error.response?.data as { detail?: string };
    if (responseData?.detail) {
      return responseData.detail;
    }
    if (error.message) {
      return error.message;
    }
  }

  // Fallback for unknown error types
  return 'An unexpected error occurred. Please try again.';
}

export const sendVerificationEmailApi = async (userId: string) => {
  const response = await api.post(`/v0/account/email/verification/send/${userId}`);
  return response.data;
};

export const verifyEmailApi = async (token: string) => {
  const response = await api.post(`/v0/account/email/verification/${token}`);
  return response.data;
};

export const sendRegistrationVerificationEmailApi = async (userId: string) => {
  const response = await api.post(`/v0/account/email/verification/register/${userId}`);
  return response.data;
};

// Invitation APIs
export const createInvitationApi = async (invitation: CreateInvitationRequest): Promise<InvitationResponse> => {
  const response = await api.post<InvitationResponse>('/v0/account/email/invitations', invitation);
  return response.data;
};

export const getInvitationsApi = async (params?: ListInvitationsParams): Promise<ListInvitationsResponse> => {
  const queryParams = new URLSearchParams();
  if (params?.skip) queryParams.append('skip', params.skip.toString());
  if (params?.limit) queryParams.append('limit', params.limit.toString());

  const response = await api.get<ListInvitationsResponse>(
    `/v0/account/email/invitations?${queryParams.toString()}`
  );
  return response.data;
};

export const acceptInvitationApi = async (token: string, data: AcceptInvitationRequest): Promise<{ message: string }> => {
  const response = await api.post(`/v0/account/email/invitations/${token}/accept`, data);
  return response.data;
};

export const getInvitationApi = async (token: string): Promise<InvitationResponse> => {
  const response = await api.get<InvitationResponse>(`/v0/account/email/invitations/${token}`);
  return response.data;
};

// Subscription APIs
export const getCustomerPortalApi = async (orgId: string): Promise<PortalSessionResponse> => {
  const response = await api.post<PortalSessionResponse>(`/v0/payments/${orgId}/customer-portal`);
  return response.data;
};

// Add these new API functions
export const getSubscriptionApi = async (orgId: string): Promise<SubscriptionResponse> => {
  const response = await api.get<SubscriptionResponse>(`/v0/payments/${orgId}/subscription`);
  return response.data;
};

export const activateSubscriptionApi = async (orgId: string): Promise<{ status: string; message: string }> => {
  const response = await api.put<{ status: string; message: string }>(`/v0/payments/${orgId}/subscription`);
  return response.data;
};

export const cancelSubscriptionApi = async (orgId: string): Promise<{ status: string; message: string }> => {
  const response = await api.delete<{ status: string; message: string }>(`/v0/payments/${orgId}/subscription`);
  return response.data;
};

// Add new API function to get current usage
export const getCurrentUsageApi = async (orgId: string): Promise<UsageResponse> => {
  const response = await api.get<UsageResponse>(`/v0/payments/${orgId}/usage`);
  return response.data;
};

export const createSubscriptionApi = async (orgId: string): Promise<{ status: string; message: string }> => {
  const response = await api.post<{ status: string; message: string }>(`/v0/payments/${orgId}/subscription`);
  return response.data;
};

// Add new API function to add credits (admin only)
export const addCreditsApi = async (orgId: string, amount: number): Promise<CreditUpdateResponse> => {
  const response = await api.post<CreditUpdateResponse>(`/v0/payments/${orgId}/credits/add`, { amount });
  return response.data;
};

export const getCreditConfigApi = async (orgId: string): Promise<CreditConfig> => {
  const response = await api.get<CreditConfig>(`/v0/payments/${orgId}/credits/config`);
  return response.data;
};

export const purchaseCreditsApi = async (orgId: string, request: {
  credits: number;
  success_url: string;
  cancel_url: string;
}) => {
  const response = await api.post(`/v0/payments/${orgId}/credits/purchase`, request);
  return response.data;
};

// Add this new API function after the existing subscription APIs
export const createCheckoutSessionApi = async (orgId: string, planId: string): Promise<PortalSessionResponse> => {
  const response = await api.post<PortalSessionResponse>(`/v0/payments/${orgId}/checkout-session`, { plan_id: planId });
  return response.data;
};

// Proxy API
export const proxyRequestApi = async (targetUrl: string, options?: {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}) => {
  const method = options?.method || 'GET';
  const config: {
    method: string;
    params: { url: string };
    data?: unknown;
    headers?: Record<string, string>;
  } = {
    method: method.toLowerCase(),
    params: { url: targetUrl }
  };

  // If there's a body, add it to the request
  if (options?.body && ['POST', 'PUT', 'PATCH'].includes(method.toUpperCase())) {
    config.data = options.body;
  }

  // Add any additional headers
  if (options?.headers) {
    config.headers = { ...config.headers, ...options.headers };
  }

  const response = await api.request({
    method: config.method,
    url: '/v0/proxy',
    params: config.params,
    data: config.data,
    headers: config.headers
  });
  return response.data;
};

// Helper function to get session token for direct fetch calls (for FormIO)
export const getSessionToken = async (): Promise<string | null> => {
  const session = await getCachedSession();
  return session?.apiAccessToken || null;
};

// Table APIs
export const createTableApi = async (table: CreateTableParams): Promise<Table> => {
  const { organizationId, ...tableConfig } = table;
  const response = await api.post<Table>(`/v0/orgs/${organizationId}/tables`, tableConfig);
  return response.data;
};

export const listTablesApi = async (params: ListTablesParams): Promise<ListTablesResponse> => {
  const { organizationId, ...rest } = params;
  const response = await api.get<ListTablesResponse>(`/v0/orgs/${organizationId}/tables`, {
    params: {
      skip: rest?.skip || 0,
      limit: rest?.limit || 10,
      tag_ids: rest?.tag_ids
    }
  });
  return response.data;
};

export const getTableApi = async (params: GetTableParams): Promise<Table> => {
  const { organizationId, tableRevId } = params;
  const response = await api.get<Table>(`/v0/orgs/${organizationId}/tables/${tableRevId}`);
  return response.data;
};

export const updateTableApi = async (params: UpdateTableParams): Promise<Table> => {
  const { organizationId, tableId, table } = params;
  const response = await api.put<Table>(`/v0/orgs/${organizationId}/tables/${tableId}`, table);
  return response.data;
};

export const deleteTableApi = async (params: DeleteTableParams) => {
  const { organizationId, tableId } = params;
  const response = await api.delete(`/v0/orgs/${organizationId}/tables/${tableId}`);
  return response.data;
};

// Table submissions
export const submitTableApi = async (params: SubmitTableParamsTable): Promise<TableSubmission> => {
  const { organizationId, documentId, submission } = params;
  const response = await api.post<TableSubmission>(
    `/v0/orgs/${organizationId}/tables/submissions/${documentId}`,
    submission
  );
  return response.data;
};

export const getTableSubmissionApi = async (params: GetTableSubmissionParams): Promise<TableSubmission | null> => {
  const { organizationId, documentId, tableRevId } = params;
  const response = await api.get<TableSubmission | null>(
    `/v0/orgs/${organizationId}/tables/submissions/${documentId}?table_revid=${tableRevId}`
  );
  return response.data;
};

export const deleteTableSubmissionApi = async (params: DeleteTableSubmissionParams): Promise<void> => {
  const { organizationId, documentId, tableRevId } = params;
  const response = await api.delete(`/v0/orgs/${organizationId}/tables/submissions/${documentId}`, {
    params: { table_revid: tableRevId }
  });
  return response.data;
};