import { HttpClient } from './http-client';
import { normalizeOcrBlocksPayload } from './ocr-blocks';
import {
  DocRouterOrgConfig,
  UploadDocumentMultipartPart,
  UploadDocumentResponse,
  UploadDocumentsResponse,
  ListDocumentsResponse,
  GetDocumentResponse,
  GetOCRMetadataResponse,
  RunLLMResponse,
  GetLLMResultResponse,
  ListTagsParams,
  ListTagsResponse,
  JsonValue,
  Tag,
  OCRBlock,
  // Forms
  CreateFormParams,
  ListFormsParams,
  ListFormsResponse,
  GetFormParams,
  UpdateFormParams,
  DeleteFormParams,
  SubmitFormParams,
  GetFormSubmissionParams,
  DeleteFormSubmissionParams,
  Form,
  FormSubmission,
  // Prompts
  CreatePromptParams,
  ListPromptsParams,
  ListPromptsResponse,
  GetPromptParams,
  UpdatePromptParams,
  DeletePromptParams,
  Prompt,
  // Schemas
  CreateSchemaParams,
  ListSchemasParams,
  ListSchemasResponse,
  GetSchemaParams,
  UpdateSchemaParams,
  DeleteSchemaParams,
  Schema,
  // Payments
  PortalSessionResponse,
  SubscriptionResponse,
  UsageResponse,
  CreditConfig,
  CreditUpdateResponse,
  UsageRangeRequest,
  UsageRangeResponse,
  // Knowledge Bases
  KnowledgeBase,
  KnowledgeBaseConfig,
  KnowledgeBaseUpdate,
  ListKnowledgeBasesParams,
  ListKnowledgeBasesResponse,
  GetKnowledgeBaseParams,
  CreateKnowledgeBaseParams,
  UpdateKnowledgeBaseParams,
  DeleteKnowledgeBaseParams,
  ListKBDocumentsParams,
  ListKBDocumentsResponse,
  ListKBDocumentChunksParams,
  ListKBChunksResponse,
  KBSearchRequest,
  KBSearchResponse,
  SearchKnowledgeBaseParams,
  ReconcileKnowledgeBaseParams,
  ReconcileKnowledgeBaseResponse,
  ReconcileAllKnowledgeBasesParams,
  ReconcileAllKnowledgeBasesResponse,
  // LLM Chat
  LLMChatRequest,
  LLMChatResponse,
  LLMChatStreamChunk,
  LLMChatStreamError,
  // KB Chat
  KBChatRequest,
  KBChatStreamChunk,
  KBChatStreamError,
  ChatThreadSummary,
  ChatThreadDetail,
  CreateChatThreadResponse,
  // LLM Models
  ListOrgLLMModelsResponse,
  // Webhooks
  WebhookEndpoint,
  CreateWebhookParams,
  UpdateWebhookParams,
  WebhookDelivery,
  WebhookDeliveryDetail,
  ListWebhookDeliveriesParams,
  ListWebhookDeliveriesResponse,
  // Flows
  FlowNodeType,
  ListNodeTypesResponse,
  FlowHeader,
  FlowRevision,
  FlowRevisionSummary,
  FlowListItem,
  ListFlowsResponse,
  ListRevisionsResponse,
  FlowExecution,
  ListExecutionsResponse,
  CreateFlowParams,
  SaveRevisionParams,
  RunFlowParams,
} from './types';

/**
 * DocRouterOrg - For organization-scoped operations with org tokens
 * Use this when you have an organization token and want to work within that org
 */
export class DocRouterOrg {
  public readonly organizationId: string;
  private http: HttpClient;

  constructor(config: DocRouterOrgConfig) {
    this.organizationId = config.organizationId;
    this.http = new HttpClient({
      baseURL: config.baseURL,
      token: config.orgToken,
      timeout: config.timeout,
      retries: config.retries,
      onAuthError: config.onAuthError,
    });
  }

  /**
   * Update the organization token
   */
  updateToken(token: string): void {
    this.http.updateToken(token);
  }

  // ---------------- Documents ----------------

  async uploadDocuments(params: { documents: Array<{ name: string; content: string; tag_ids?: string[]; metadata?: Record<string, string>; }>; }): Promise<UploadDocumentsResponse> {
    const documentsPayload = params.documents.map(doc => {
      // Handle both plain base64 and data URLs
      let base64Content: string;
      if (doc.content.startsWith('data:')) {
        // Extract base64 from data URL (e.g., "data:application/pdf;base64,JVBERi0xLjQK...")
        base64Content = doc.content.split(',')[1];
      } else {
        // Plain base64 string
        base64Content = doc.content;
      }

      const payload: {
        name: string;
        content: string;
        tag_ids?: string[];
        metadata?: Record<string, string>;
      } = {
        name: doc.name,
        content: base64Content,
      };
      if (doc.tag_ids && doc.tag_ids.length > 0) payload.tag_ids = doc.tag_ids;
      if (doc.metadata) payload.metadata = doc.metadata;
      return payload;
    });

    return this.http.post<UploadDocumentsResponse>(
      `/v0/orgs/${this.organizationId}/documents`,
      { documents: documentsPayload }
    );
  }

  /**
   * Upload a single document via multipart/form-data (no base64).
   */
  async uploadDocumentMultipart(params: UploadDocumentMultipartPart): Promise<UploadDocumentResponse> {
    const form = new FormData();
    form.append('file', params.file, params.name);
    if (params.tag_ids?.length) form.append('tag_ids', JSON.stringify(params.tag_ids));
    if (params.metadata && Object.keys(params.metadata).length) form.append('metadata', JSON.stringify(params.metadata));
    return this.http.postFormData<UploadDocumentResponse>(
      `/v0/orgs/${this.organizationId}/documents/multipart`,
      form
    );
  }

  /** Upload multiple documents one at a time. */
  async uploadDocumentsMultipart(params: {
    documents: UploadDocumentMultipartPart[];
  }): Promise<UploadDocumentsResponse> {
    const { documents } = params;
    if (documents.length === 0) {
      throw new Error('uploadDocumentsMultipart requires at least one document');
    }
    const results = await Promise.all(documents.map((doc) => this.uploadDocumentMultipart(doc)));
    return { documents: results.map((r) => r.document) };
  }

  async listDocuments(params?: {
    skip?: number;
    limit?: number;
    tagIds?: string;
    nameSearch?: string;
    metadataSearch?: string;
    sort?: string;
    filters?: string;
  }): Promise<ListDocumentsResponse> {
    const queryParams: Record<string, string | number | undefined> = {
      skip: params?.skip || 0,
      limit: params?.limit || 10,
    };
    if (params?.tagIds) queryParams.tag_ids = params.tagIds;
    if (params?.nameSearch) queryParams.name_search = params.nameSearch;
    if (params?.metadataSearch) queryParams.metadata_search = params.metadataSearch;
    if (params?.sort) queryParams.sort = params.sort;
    if (params?.filters) queryParams.filters = params.filters;

    // Debug aid: helps verify sort/filters reach the HTTP layer.
    // Safe in prod (no secrets), but noisy; can be removed once stable.
    if (typeof window !== 'undefined') {
      // eslint-disable-next-line no-console
      console.debug('DocRouterOrg.listDocuments params', queryParams);
    }

    return this.http.get<ListDocumentsResponse>(`/v0/orgs/${this.organizationId}/documents`, {
      params: queryParams
    });
  }

  async getDocument(params: { documentId: string; fileType: string; includeContent?: boolean }): Promise<GetDocumentResponse> {
    const { documentId, fileType, includeContent = true } = params;
    const query = new URLSearchParams({ file_type: fileType });
    if (includeContent === false) {
      query.set('include_content', 'false');
    }
    const response = await this.http.get<{
      id: string;
      pdf_id: string;
      document_name: string;
      upload_date: string;
      uploaded_by: string;
      state: string;
      tag_ids: string[];
      type: string | null;
      metadata: Record<string, string>;
      content: string | null;
    }>(`/v0/orgs/${this.organizationId}/documents/${documentId}?${query.toString()}`);

    let content: ArrayBuffer | null = null;
    if (response.content != null && response.content.length > 0) {
      const binaryContent = atob(response.content);
      const len = binaryContent.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryContent.charCodeAt(i);
      }
      content = bytes.buffer;
    }

    return {
      id: response.id,
      pdf_id: response.pdf_id,
      document_name: response.document_name,
      upload_date: response.upload_date,
      uploaded_by: response.uploaded_by,
      state: response.state,
      tag_ids: response.tag_ids,
      type: response.type ?? null,
      metadata: response.metadata,
      content
    };
  }

  async getDocumentFile(params: { documentId: string; fileType?: string }): Promise<ArrayBuffer> {
    const { documentId, fileType = 'pdf' } = params;
    return this.http.getBinary(
      `/v0/orgs/${this.organizationId}/documents/${documentId}/file?file_type=${fileType}`
    );
  }

  async updateDocument(params: { documentId: string; documentName?: string; tagIds?: string[]; metadata?: Record<string, string>; }) {
    const { documentId, documentName, tagIds, metadata } = params;
    const updateData: { tag_ids?: string[]; document_name?: string; metadata?: Record<string, string> } = {};
    if (documentName !== undefined) updateData.document_name = documentName;
    if (tagIds !== undefined) updateData.tag_ids = tagIds;
    if (metadata !== undefined) updateData.metadata = metadata;
    return this.http.put(`/v0/orgs/${this.organizationId}/documents/${documentId}`, updateData);
  }

  async deleteDocument(params: { documentId: string; }) {
    const { documentId } = params;
    return this.http.delete(`/v0/orgs/${this.organizationId}/documents/${documentId}`);
  }

  // ---------------- OCR ----------------

  /**
   * Textract-oriented block list for search/bbox (WORD/LINE blocks). For Mistral/LLM/PyMuPDF payloads
   * (`{ pages: [...] }`), the download/json API still returns that JSON, but this method
   * normalizes unknown shapes to `[]` — use {@link getOCRStoredPayload} for a faithful export.
   *
   * @param format - 'gzip' (default) requests compressed response for smaller transfer; 'plain' for raw JSON (backward compatible).
   * Browser/axios automatically decompresses gzip responses.
   */
  async getOCRBlocks(params: { documentId: string; format?: 'plain' | 'gzip' }): Promise<OCRBlock[]> {
    const { documentId, format = 'gzip' } = params;
    const raw = await this.http.get<unknown>(
      `/v0/orgs/${this.organizationId}/ocr/download/json/${documentId}`,
      { params: { format } }
    );
    return normalizeOcrBlocksPayload(raw);
  }

  /**
   * Same HTTP resource as {@link getOCRBlocks} (`/ocr/download/json/...`) but returns the JSON
   * body without normalizing — suitable for saving `_ocr.json` (Textract list, Mistral/LLM pages, etc.).
   */
  async getOCRStoredPayload(params: { documentId: string; format?: 'plain' | 'gzip' }): Promise<unknown> {
    const { documentId, format = 'gzip' } = params;
    return this.http.get<unknown>(
      `/v0/orgs/${this.organizationId}/ocr/download/json/${documentId}`,
      { params: { format } }
    );
  }

  async getOCRText(params: { documentId: string; pageNum?: number; }): Promise<string> {
    const { documentId, pageNum } = params;
    const url = `/v0/orgs/${this.organizationId}/ocr/download/text/${documentId}${pageNum ? `?page_num=${pageNum}` : ''}`;
    return this.http.get<string>(url);
  }

  async getOCRMetadata(params: { documentId: string; }): Promise<GetOCRMetadataResponse> {
    const { documentId } = params;
    return this.http.get<GetOCRMetadataResponse>(`/v0/orgs/${this.organizationId}/ocr/download/metadata/${documentId}`);
  }

  async runOCR(params: { documentId: string; force?: boolean; ocrOnly?: boolean }): Promise<void> {
    const { documentId, force, ocrOnly } = params;
    const queryParams: Record<string, unknown> = {};
    if (force !== undefined) queryParams.force = force;
    if (ocrOnly !== undefined) queryParams.ocr_only = ocrOnly;
    await this.http.post<void>(
      `/v0/orgs/${this.organizationId}/ocr/run/${documentId}`,
      null,
      { params: queryParams },
    );
  }

  /**
   * On-the-fly Markdown linearization from stored OCR (textractor).
   */
  async getOCRExportMarkdown(params: { documentId: string }): Promise<string> {
    const { documentId } = params;
    return this.http.get<string>(
      `/v0/orgs/${this.organizationId}/ocr/export/markdown/${documentId}`,
      { responseType: 'text' },
    );
  }

  /**
   * On-the-fly HTML linearization from stored OCR (textractor).
   */
  async getOCRExportHtml(params: { documentId: string }): Promise<string> {
    const { documentId } = params;
    return this.http.get<string>(
      `/v0/orgs/${this.organizationId}/ocr/export/html/${documentId}`,
      { responseType: 'text' },
    );
  }

  /**
   * Excel export of detected OCR tables (one sheet per table unless tableIndex is set).
   */
  async getOCRExportTablesXlsx(params: {
    documentId: string;
    tableIndex?: number;
  }): Promise<Blob> {
    const { documentId, tableIndex } = params;
    return this.http.get<Blob>(
      `/v0/orgs/${this.organizationId}/ocr/export/tables.xlsx/${documentId}`,
      {
        responseType: 'blob',
        params: tableIndex !== undefined ? { table_index: tableIndex } : undefined,
      },
    );
  }

  // ---------------- LLM ----------------

  async runLLM(params: { documentId: string; promptRevId: string; force?: boolean; }): Promise<RunLLMResponse> {
    const { documentId, promptRevId, force } = params;
    return this.http.post<RunLLMResponse>(
      `/v0/orgs/${this.organizationId}/llm/run/${documentId}`,
      {},
      { params: { prompt_revid: promptRevId, force } }
    );
  }

  async getLLMResult(params: { documentId: string; promptRevId: string; fallback?: boolean; }): Promise<GetLLMResultResponse> {
    const { documentId, promptRevId, fallback } = params;
    return this.http.get<GetLLMResultResponse>(
      `/v0/orgs/${this.organizationId}/llm/result/${documentId}`,
      { params: { prompt_revid: promptRevId, fallback } }
    );
  }

  async updateLLMResult({
    documentId,
    promptId,
    result,
    isVerified = false
  }: { documentId: string; promptId: string; result: Record<string, JsonValue>; isVerified?: boolean; }): Promise<GetLLMResultResponse> {
    const response = await this.http.put<GetLLMResultResponse>(
      `/v0/orgs/${this.organizationId}/llm/result/${documentId}`,
      { updated_llm_result: result, is_verified: isVerified },
      { params: { prompt_revid: promptId } }
    );
    return response;
  }

  async deleteLLMResult(params: { documentId: string; promptId: string; }) {
    const { documentId, promptId } = params;
    return this.http.delete(
      `/v0/orgs/${this.organizationId}/llm/result/${documentId}`,
      { params: { prompt_revid: promptId } }
    );
  }

  async downloadAllLLMResults(params: { documentId: string; }) {
    const { documentId } = params;
    return this.http.get(
      `/v0/orgs/${this.organizationId}/llm/results/${documentId}/download`,
      { responseType: 'blob' as const }
    );
  }

  // ---------------- Prompts ----------------

  async createPrompt(params: Omit<CreatePromptParams, 'organizationId'>): Promise<Prompt> {
    const { prompt } = params;
    return this.http.post<Prompt>(`/v0/orgs/${this.organizationId}/prompts`, prompt);
  }

  async listPrompts(params?: Omit<ListPromptsParams, 'organizationId'>): Promise<ListPromptsResponse> {
    const { skip, limit, document_id, tag_ids, nameSearch } = params || {};
    return this.http.get<ListPromptsResponse>(`/v0/orgs/${this.organizationId}/prompts`, {
      params: {
        skip: skip || 0,
        limit: limit || 10,
        document_id,
        tag_ids,
        name_search: nameSearch
      }
    });
  }

  async getPrompt(params: Omit<GetPromptParams, 'organizationId'>): Promise<Prompt> {
    const { promptRevId } = params;
    return this.http.get<Prompt>(`/v0/orgs/${this.organizationId}/prompts/${promptRevId}`);
  }

  async updatePrompt(params: Omit<UpdatePromptParams, 'organizationId'>): Promise<Prompt> {
    const { promptId, prompt } = params;
    return this.http.put<Prompt>(`/v0/orgs/${this.organizationId}/prompts/${promptId}`, prompt);
  }

  async deletePrompt(params: Omit<DeletePromptParams, 'organizationId'>): Promise<{ message: string }> {
    const { promptId } = params;
    return this.http.delete<{ message: string }>(`/v0/orgs/${this.organizationId}/prompts/${promptId}`);
  }

  async listPromptVersions(params: { promptId: string }): Promise<ListPromptsResponse> {
    const { promptId } = params;
    return this.http.get<ListPromptsResponse>(`/v0/orgs/${this.organizationId}/prompts/${promptId}/versions`);
  }

  // ---------------- Tags ----------------

  async createTag(params: { tag: Omit<Tag, 'id' | 'created_at' | 'updated_at'>; }): Promise<Tag> {
    const { tag } = params;
    return this.http.post<Tag>(`/v0/orgs/${this.organizationId}/tags`, tag);
  }

  async getTag({ tagId }: { tagId: string; }): Promise<Tag> {
    return this.http.get<Tag>(`/v0/orgs/${this.organizationId}/tags/${tagId}`);
  }

  async listTags(params?: ListTagsParams): Promise<ListTagsResponse> {
    const queryParams: Record<string, string | number | undefined> = {
      skip: params?.skip || 0,
      limit: params?.limit || 10,
    };
    if (params?.nameSearch) queryParams.name_search = params.nameSearch;
    if (params?.sort) queryParams.sort = params.sort;
    if (params?.filters) queryParams.filters = params.filters;

    return this.http.get<ListTagsResponse>(`/v0/orgs/${this.organizationId}/tags`, {
      params: queryParams,
    });
  }

  async updateTag(params: { tagId: string; tag: Partial<Omit<Tag, 'id' | 'created_at' | 'updated_at'>>; }): Promise<Tag> {
    const { tagId, tag } = params;
    return this.http.put<Tag>(`/v0/orgs/${this.organizationId}/tags/${tagId}`, tag);
  }

  async deleteTag(params: { tagId: string; }): Promise<{ message: string }> {
    const { tagId } = params;
    return this.http.delete<{ message: string }>(`/v0/orgs/${this.organizationId}/tags/${tagId}`);
  }

  // ---------------- Forms ----------------

  async createForm(form: Omit<CreateFormParams, 'organizationId'>): Promise<Form> {
    const { name, response_format } = form;
    return this.http.post<Form>(`/v0/orgs/${this.organizationId}/forms`, { name, response_format });
  }

  async listForms(params?: Omit<ListFormsParams, 'organizationId'>): Promise<ListFormsResponse> {
    const { skip, limit, tag_ids } = params || {};
    return this.http.get<ListFormsResponse>(`/v0/orgs/${this.organizationId}/forms`, {
      params: { skip: skip || 0, limit: limit || 10, tag_ids }
    });
  }

  async getForm(params: Omit<GetFormParams, 'organizationId'>): Promise<Form> {
    const { formRevId } = params;
    return this.http.get<Form>(`/v0/orgs/${this.organizationId}/forms/${formRevId}`);
  }

  async updateForm(params: Omit<UpdateFormParams, 'organizationId'>): Promise<Form> {
    const { formId, form } = params;
    return this.http.put<Form>(`/v0/orgs/${this.organizationId}/forms/${formId}`, form);
  }

  async deleteForm(params: Omit<DeleteFormParams, 'organizationId'>): Promise<{ message: string }> {
    const { formId } = params;
    return this.http.delete<{ message: string }>(`/v0/orgs/${this.organizationId}/forms/${formId}`);
  }

  async listFormVersions(params: { formId: string }): Promise<ListFormsResponse> {
    const { formId } = params;
    return this.http.get<ListFormsResponse>(`/v0/orgs/${this.organizationId}/forms/${formId}/versions`);
  }

  async submitForm(params: Omit<SubmitFormParams, 'organizationId'>): Promise<FormSubmission> {
    const { documentId, formRevId, submission_data, submitted_by } = params;
    return this.http.post<FormSubmission>(`/v0/orgs/${this.organizationId}/forms/submissions/${documentId}`, {
      form_revid: formRevId,
      submission_data: submission_data,
      submitted_by: submitted_by
    });
  }

  async getFormSubmission(params: Omit<GetFormSubmissionParams, 'organizationId'>): Promise<FormSubmission | null> {
    const { documentId, formRevId } = params;
    return this.http.get<FormSubmission | null>(`/v0/orgs/${this.organizationId}/forms/submissions/${documentId}?form_revid=${formRevId}`);
  }

  async deleteFormSubmission(params: Omit<DeleteFormSubmissionParams, 'organizationId'>): Promise<void> {
    const { documentId, formRevId } = params;
    await this.http.delete(`/v0/orgs/${this.organizationId}/forms/submissions/${documentId}`, { params: { form_revid: formRevId } });
  }


  // ---------------- Schemas ----------------

  async createSchema(schema: Omit<CreateSchemaParams, 'organizationId'>): Promise<Schema> {
    return this.http.post<Schema>(`/v0/orgs/${this.organizationId}/schemas`, schema);
  }

  async listSchemas(params: Omit<ListSchemasParams, 'organizationId'>): Promise<ListSchemasResponse> {
    const { skip, limit, nameSearch } = params || {};
    return this.http.get<ListSchemasResponse>(`/v0/orgs/${this.organizationId}/schemas`, {
      params: { skip: skip || 0, limit: limit || 10, name_search: nameSearch }
    });
  }

  async getSchema(params: Omit<GetSchemaParams, 'organizationId'>): Promise<Schema> {
    const { schemaRevId } = params;
    return this.http.get<Schema>(`/v0/orgs/${this.organizationId}/schemas/${schemaRevId}`);
  }

  async updateSchema(params: Omit<UpdateSchemaParams, 'organizationId'>): Promise<Schema> {
    const { schemaId, schema } = params;
    return this.http.put<Schema>(`/v0/orgs/${this.organizationId}/schemas/${schemaId}`, schema);
  }

  async deleteSchema(params: Omit<DeleteSchemaParams, 'organizationId'>): Promise<{ message: string }> {
    const { schemaId } = params;
    return this.http.delete<{ message: string }>(`/v0/orgs/${this.organizationId}/schemas/${schemaId}`);
  }

  async validateAgainstSchema(params: { schemaRevId: string; data: Record<string, unknown> }): Promise<{ valid: boolean; errors?: string[] }> {
    const { schemaRevId, data } = params;
    return this.http.post<{ valid: boolean; errors?: string[] }>(`/v0/orgs/${this.organizationId}/schemas/${schemaRevId}/validate`, { data });
  }

  async listSchemaVersions(params: { schemaId: string }): Promise<ListSchemasResponse> {
    const { schemaId } = params;
    return this.http.get<ListSchemasResponse>(`/v0/orgs/${this.organizationId}/schemas/${schemaId}/versions`);
  }

  // ---------------- Knowledge Bases ----------------

  async createKnowledgeBase(params: Omit<CreateKnowledgeBaseParams, 'organizationId'>): Promise<KnowledgeBase> {
    const { kb } = params;
    return this.http.post<KnowledgeBase>(`/v0/orgs/${this.organizationId}/knowledge-bases`, kb);
  }

  async listKnowledgeBases(params?: Omit<ListKnowledgeBasesParams, 'organizationId'>): Promise<ListKnowledgeBasesResponse> {
    const { skip, limit, name_search } = params || {};
    return this.http.get<ListKnowledgeBasesResponse>(`/v0/orgs/${this.organizationId}/knowledge-bases`, {
      params: {
        skip: skip || 0,
        limit: limit || 10,
        name_search: name_search
      }
    });
  }

  async getKnowledgeBase(params: Omit<GetKnowledgeBaseParams, 'organizationId'>): Promise<KnowledgeBase> {
    const { kbId } = params;
    return this.http.get<KnowledgeBase>(`/v0/orgs/${this.organizationId}/knowledge-bases/${kbId}`);
  }

  async updateKnowledgeBase(params: Omit<UpdateKnowledgeBaseParams, 'organizationId'>): Promise<KnowledgeBase> {
    const { kbId, update } = params;
    return this.http.put<KnowledgeBase>(`/v0/orgs/${this.organizationId}/knowledge-bases/${kbId}`, update);
  }

  async deleteKnowledgeBase(params: Omit<DeleteKnowledgeBaseParams, 'organizationId'>): Promise<{ message: string }> {
    const { kbId } = params;
    return this.http.delete<{ message: string }>(`/v0/orgs/${this.organizationId}/knowledge-bases/${kbId}`);
  }

  async listKBDocuments(params: Omit<ListKBDocumentsParams, 'organizationId'>): Promise<ListKBDocumentsResponse> {
    const { kbId, skip, limit } = params;
    return this.http.get<ListKBDocumentsResponse>(`/v0/orgs/${this.organizationId}/knowledge-bases/${kbId}/documents`, {
      params: {
        skip: skip || 0,
        limit: limit || 10
      }
    });
  }

  async getKBDocumentChunks(params: Omit<ListKBDocumentChunksParams, 'organizationId'>): Promise<ListKBChunksResponse> {
    const { kbId, documentId, skip, limit } = params;
    return this.http.get<ListKBChunksResponse>(`/v0/orgs/${this.organizationId}/knowledge-bases/${kbId}/documents/${documentId}/chunks`, {
      params: {
        skip: skip || 0,
        limit: limit || 100
      }
    });
  }

  async searchKnowledgeBase(params: Omit<SearchKnowledgeBaseParams, 'organizationId'>): Promise<KBSearchResponse> {
    const { kbId, search } = params;
    return this.http.post<KBSearchResponse>(`/v0/orgs/${this.organizationId}/knowledge-bases/${kbId}/search`, search);
  }

  async reconcileKnowledgeBase(params: Omit<ReconcileKnowledgeBaseParams, 'organizationId'>): Promise<ReconcileKnowledgeBaseResponse> {
    const { kbId, dry_run } = params;
    return this.http.post<ReconcileKnowledgeBaseResponse>(`/v0/orgs/${this.organizationId}/knowledge-bases/${kbId}/reconcile`, {}, {
      params: { dry_run: dry_run || false }
    });
  }

  async reconcileAllKnowledgeBases(params?: Omit<ReconcileAllKnowledgeBasesParams, 'organizationId'>): Promise<ReconcileAllKnowledgeBasesResponse> {
    const { dry_run } = params || {};
    return this.http.post<ReconcileAllKnowledgeBasesResponse>(`/v0/orgs/${this.organizationId}/knowledge-bases/reconcile-all`, {}, {
      params: { dry_run: dry_run || false }
    });
  }

  // ---------------- Payments ----------------

  async getCustomerPortal(): Promise<PortalSessionResponse> {
    return this.http.post<PortalSessionResponse>(`/v0/orgs/${this.organizationId}/payments/customer-portal`, {});
  }

  async getSubscription(): Promise<SubscriptionResponse> {
    return this.http.get<SubscriptionResponse>(`/v0/orgs/${this.organizationId}/payments/subscription`);
  }

  async activateSubscription(): Promise<{ status: string; message: string }> {
    return this.http.put<{ status: string; message: string }>(`/v0/orgs/${this.organizationId}/payments/subscription`, {});
  }

  async cancelSubscription(): Promise<{ status: string; message: string }> {
    return this.http.delete<{ status: string; message: string }>(`/v0/orgs/${this.organizationId}/payments/subscription`);
  }


  async getCurrentUsage(): Promise<UsageResponse> {
    return this.http.get<UsageResponse>(`/v0/orgs/${this.organizationId}/payments/usage`);
  }

  async addCredits(amount: number): Promise<CreditUpdateResponse> {
    return this.http.post<CreditUpdateResponse>(`/v0/orgs/${this.organizationId}/payments/credits/add`, { amount });
  }

  async getCreditConfig(): Promise<CreditConfig> {
    return this.http.get<CreditConfig>(`/v0/orgs/${this.organizationId}/payments/credits/config`);
  }

  async purchaseCredits(request: { credits: number; success_url: string; cancel_url: string; }) {
    return this.http.post(`/v0/orgs/${this.organizationId}/payments/credits/purchase`, request);
  }

  async getUsageRange(request: UsageRangeRequest): Promise<UsageRangeResponse> {
    return this.http.get<UsageRangeResponse>(`/v0/orgs/${this.organizationId}/payments/usage/range`, { params: request });
  }

  async createCheckoutSession(planId: string): Promise<PortalSessionResponse> {
    return this.http.post<PortalSessionResponse>(`/v0/orgs/${this.organizationId}/payments/checkout-session`, { plan_id: planId });
  }

  // ---------------- LLM Chat (Org) ----------------

  async runLLMChat(request: LLMChatRequest): Promise<LLMChatResponse> {
    return this.http.post(`/v0/orgs/${this.organizationId}/llm/run`, request);
  }

  // ---------------- LLM Models (Org) ----------------

  async listLLMModels(): Promise<ListOrgLLMModelsResponse> {
    return this.http.get<ListOrgLLMModelsResponse>(`/v0/orgs/${this.organizationId}/llm/models`);
  }

  async runLLMChatStream(
    request: LLMChatRequest,
    onChunk: (chunk: LLMChatStreamChunk | LLMChatStreamError) => void,
    onError?: (error: Error) => void,
    abortSignal?: AbortSignal
  ): Promise<void> {
    const streamingRequest = { ...request, stream: true };
    return this.http.stream<LLMChatStreamChunk | LLMChatStreamError>(
      `/v0/orgs/${this.organizationId}/llm/run`,
      streamingRequest,
      onChunk,
      onError,
      abortSignal
    );
  }

  /**
   * Run KB chat with streaming (organization level)
   */
  async runKBChatStream(
    kbId: string,
    request: KBChatRequest,
    onChunk: (chunk: KBChatStreamChunk | KBChatStreamError) => void,
    onError?: (error: Error) => void,
    abortSignal?: AbortSignal
  ): Promise<void> {
    const streamingRequest = { ...request, stream: true };
    return this.http.stream<KBChatStreamChunk | KBChatStreamError>(
      `/v0/orgs/${this.organizationId}/knowledge-bases/${kbId}/chat`,
      streamingRequest,
      onChunk,
      onError,
      abortSignal
    );
  }

  /** List KB chat threads (most recent first). */
  async listKbChatThreads(kbId: string, params?: { limit?: number }): Promise<ChatThreadSummary[]> {
    return this.http.get<ChatThreadSummary[]>(
      `/v0/orgs/${this.organizationId}/knowledge-bases/${kbId}/chat/threads`,
      { params: params as Record<string, string | number | undefined> }
    );
  }

  /** Create a KB chat thread. */
  async createKbChatThread(kbId: string, body?: { title?: string | null }): Promise<CreateChatThreadResponse> {
    return this.http.post<CreateChatThreadResponse>(
      `/v0/orgs/${this.organizationId}/knowledge-bases/${kbId}/chat/threads`,
      body ?? {}
    );
  }

  /** Load a KB chat thread with messages. */
  async getKbChatThread(kbId: string, threadId: string): Promise<ChatThreadDetail> {
    return this.http.get<ChatThreadDetail>(
      `/v0/orgs/${this.organizationId}/knowledge-bases/${kbId}/chat/threads/${threadId}`
    );
  }

  /** Delete a KB chat thread. */
  async deleteKbChatThread(kbId: string, threadId: string): Promise<{ ok: boolean }> {
    return this.http.delete<{ ok: boolean }>(
      `/v0/orgs/${this.organizationId}/knowledge-bases/${kbId}/chat/threads/${threadId}`
    );
  }

  // ---------------- Webhooks ----------------

  /**
   * List all webhook endpoints for this organization.
   */
  async listWebhooks(): Promise<WebhookEndpoint[]> {
    return this.http.get<WebhookEndpoint[]>(`/v0/orgs/${this.organizationId}/webhooks`);
  }

  /**
   * Create a new webhook endpoint for this organization.
   */
  async createWebhook(params: CreateWebhookParams): Promise<WebhookEndpoint> {
    const body: Record<string, unknown> = {
      name: params.name,
      enabled: params.enabled ?? true,
      url: params.url,
      events: params.events,
      auth_type: params.auth_type,
      auth_header_name: params.auth_header_name,
      auth_header_value: params.auth_header_value,
      secret: params.secret,
    };
    return this.http.post<WebhookEndpoint>(`/v0/orgs/${this.organizationId}/webhooks`, body);
  }

  /**
   * Get a single webhook endpoint by ID.
   */
  async getWebhook(webhookId: string): Promise<WebhookEndpoint> {
    return this.http.get<WebhookEndpoint>(`/v0/orgs/${this.organizationId}/webhooks/${webhookId}`);
  }

  /**
   * Update an existing webhook endpoint.
   */
  async updateWebhook(params: UpdateWebhookParams): Promise<WebhookEndpoint> {
    const { webhookId, ...rest } = params;
    return this.http.put<WebhookEndpoint>(
      `/v0/orgs/${this.organizationId}/webhooks/${webhookId}`,
      rest,
    );
  }

  /**
   * Delete a webhook endpoint.
   */
  async deleteWebhook(webhookId: string): Promise<void> {
    await this.http.delete(`/v0/orgs/${this.organizationId}/webhooks/${webhookId}`);
  }

  /**
   * Trigger a test event for a specific webhook endpoint.
   */
  async testWebhook(webhookId: string): Promise<{ status: string; delivery_id: string }> {
    return this.http.post<{ status: string; delivery_id: string }>(
      `/v0/orgs/${this.organizationId}/webhooks/${webhookId}/test`,
      {},
    );
  }

  /**
   * List webhook deliveries for this organization, optionally filtered by status, event type, or webhook_id.
   */
  async listWebhookDeliveries(
    params?: ListWebhookDeliveriesParams,
  ): Promise<ListWebhookDeliveriesResponse> {
    const { status, event_type, webhook_id, skip, limit } = params || {};
    const query: Record<string, unknown> = {};
    if (status) query.status = status;
    if (event_type) query.event_type = event_type;
    if (webhook_id) query.webhook_id = webhook_id;
    if (skip !== undefined) query.skip = skip;
    if (limit !== undefined) query.limit = limit;
    return this.http.get<ListWebhookDeliveriesResponse>(
      `/v0/orgs/${this.organizationId}/webhooks/deliveries`,
      { params: query },
    );
  }

  /**
   * Get a single webhook delivery by ID.
   */
  async getWebhookDelivery(deliveryId: string): Promise<WebhookDeliveryDetail> {
    return this.http.get<WebhookDeliveryDetail>(
      `/v0/orgs/${this.organizationId}/webhooks/deliveries/${deliveryId}`,
    );
  }

  /**
   * Retry a failed webhook delivery.
   */
  async retryWebhookDelivery(
    deliveryId: string,
  ): Promise<{ status: string; delivery_id: string }> {
    return this.http.post<{ status: string; delivery_id: string }>(
      `/v0/orgs/${this.organizationId}/webhooks/deliveries/${deliveryId}/retry`,
      {},
    );
  }

  // ---------------- Flows ----------------

  async listFlowNodeTypes(): Promise<ListNodeTypesResponse> {
    return this.http.get<ListNodeTypesResponse>(`/v0/orgs/${this.organizationId}/flows/node-types`);
  }

  async createFlow(params: CreateFlowParams): Promise<{ flow: FlowHeader }> {
    return this.http.post<{ flow: FlowHeader }>(`/v0/orgs/${this.organizationId}/flows`, params);
  }

  async listFlows(params?: { limit?: number; offset?: number }): Promise<ListFlowsResponse> {
    return this.http.get<ListFlowsResponse>(`/v0/orgs/${this.organizationId}/flows`, {
      params: {
        limit: params?.limit ?? 20,
        offset: params?.offset ?? 0,
      },
    });
  }

  async getFlow(flowId: string): Promise<FlowListItem> {
    return this.http.get<FlowListItem>(`/v0/orgs/${this.organizationId}/flows/${flowId}`);
  }

  async patchFlow(flowId: string, params: { name: string }): Promise<FlowListItem> {
    return this.http.patch<FlowListItem>(`/v0/orgs/${this.organizationId}/flows/${flowId}`, params);
  }

  async deleteFlow(flowId: string): Promise<void> {
    await this.http.delete(`/v0/orgs/${this.organizationId}/flows/${flowId}`);
  }

  async saveRevision(
    flowId: string,
    params: SaveRevisionParams,
  ): Promise<{ flow: FlowHeader; revision: FlowRevision | null }> {
    return this.http.put<{ flow: FlowHeader; revision: FlowRevision | null }>(
      `/v0/orgs/${this.organizationId}/flows/${flowId}`,
      params,
    );
  }

  async listRevisions(flowId: string, params?: { limit?: number; offset?: number }): Promise<ListRevisionsResponse> {
    return this.http.get<ListRevisionsResponse>(`/v0/orgs/${this.organizationId}/flows/${flowId}/revisions`, {
      params: {
        limit: params?.limit ?? 50,
        offset: params?.offset ?? 0,
      },
    });
  }

  async getRevision(flowId: string, flowRevid: string): Promise<FlowRevision> {
    return this.http.get<FlowRevision>(`/v0/orgs/${this.organizationId}/flows/${flowId}/revisions/${flowRevid}`);
  }

  async activateFlow(flowId: string, flowRevid?: string): Promise<FlowListItem> {
    return this.http.post<FlowListItem>(`/v0/orgs/${this.organizationId}/flows/${flowId}/activate`, {
      flow_revid: flowRevid ?? null,
    });
  }

  async deactivateFlow(flowId: string): Promise<FlowListItem> {
    return this.http.post<FlowListItem>(`/v0/orgs/${this.organizationId}/flows/${flowId}/deactivate`, {});
  }

  async runFlow(flowId: string, params?: RunFlowParams): Promise<{ execution_id: string }> {
    return this.http.post<{ execution_id: string }>(`/v0/orgs/${this.organizationId}/flows/${flowId}/run`, {
      flow_revid: params?.flow_revid ?? null,
      document_id: params?.document_id ?? null,
    });
  }

  async listExecutions(flowId: string, params?: { limit?: number; offset?: number }): Promise<ListExecutionsResponse> {
    return this.http.get<ListExecutionsResponse>(`/v0/orgs/${this.organizationId}/flows/${flowId}/executions`, {
      params: {
        limit: params?.limit ?? 50,
        offset: params?.offset ?? 0,
      },
    });
  }

  async getExecution(flowId: string, executionId: string): Promise<FlowExecution> {
    return this.http.get<FlowExecution>(`/v0/orgs/${this.organizationId}/flows/${flowId}/executions/${executionId}`);
  }

  async stopExecution(flowId: string, executionId: string): Promise<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(
      `/v0/orgs/${this.organizationId}/flows/${flowId}/executions/${executionId}/stop`,
      {},
    );
  }

  /**
   * Get the current HTTP client (for advanced usage)
   */
  getHttpClient(): HttpClient {
    return this.http;
  }
}
