import { DocRouterAccount, DocRouterOrg } from '../../src';
import type { GetLLMResultResponse } from '../../src';

describe('SDK Client Unit Tests', () => {
  describe('DocRouterAccount', () => {
    test('should create instance with account token', () => {
      const client = new DocRouterAccount({
        baseURL: 'https://api.example.com',
        accountToken: 'account-token'
      });

      expect(client).toBeDefined();
    });

    test('should update account token', () => {
      const client = new DocRouterAccount({
        baseURL: 'https://api.example.com',
        accountToken: 'initial-token'
      });

      client.updateToken('new-token');
      expect(client).toBeDefined();
    });

    test('should have all invitation APIs', () => {
      const client = new DocRouterAccount({
        baseURL: 'https://api.example.com',
        accountToken: 'account-token'
      });

      expect(typeof client.createInvitation).toBe('function');
      expect(typeof client.getInvitations).toBe('function');
      expect(typeof client.getInvitation).toBe('function');
      expect(typeof client.acceptInvitation).toBe('function');
    });

    test('should have all payment APIs', () => {
      const client = new DocRouterAccount({
        baseURL: 'https://api.example.com',
        accountToken: 'account-token'
      });

      expect(typeof client.getCustomerPortal).toBe('function');
      expect(typeof client.getSubscription).toBe('function');
      expect(typeof client.activateSubscription).toBe('function');
      expect(typeof client.cancelSubscription).toBe('function');
      expect(typeof client.getCurrentUsage).toBe('function');
      expect(typeof client.addCredits).toBe('function');
      expect(typeof client.getCreditConfig).toBe('function');
      expect(typeof client.purchaseCredits).toBe('function');
      expect(typeof client.getUsageRange).toBe('function');
      expect(typeof client.createCheckoutSession).toBe('function');
    });
  });

  describe('DocRouterOrg', () => {
    test('should create instance with org token', () => {
      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'org-token',
        organizationId: 'org-123'
      });

      expect(client).toBeDefined();
      expect(client.organizationId).toBe('org-123');
      // flattened API surface
      expect(typeof client.uploadDocuments).toBe('function');
      expect(typeof client.uploadDocumentsMultipart).toBe('function');
      expect(typeof client.listDocuments).toBe('function');
      expect(typeof client.getDocument).toBe('function');
      expect(typeof client.updateDocument).toBe('function');
      expect(typeof client.deleteDocument).toBe('function');
      expect(typeof client.getOCRBlocks).toBe('function');
      expect(typeof client.getOCRText).toBe('function');
      expect(typeof client.getOCRMetadata).toBe('function');
      expect(typeof client.getOCRExportMarkdown).toBe('function');
      expect(typeof client.getOCRExportHtml).toBe('function');
      expect(typeof client.getOCRExportTablesXlsx).toBe('function');
      expect(typeof client.runLLM).toBe('function');
      expect(typeof client.getLLMResult).toBe('function');
      expect(typeof client.updateLLMResult).toBe('function');
      expect(typeof client.deleteLLMResult).toBe('function');
      expect(typeof client.downloadAllLLMResults).toBe('function');
      expect(typeof client.createTag).toBe('function');
      expect(typeof client.getTag).toBe('function');
      expect(typeof client.listTags).toBe('function');
      expect(typeof client.updateTag).toBe('function');
      expect(typeof client.deleteTag).toBe('function');
      expect(typeof client.createKnowledgeBase).toBe('function');
      expect(typeof client.listKnowledgeBases).toBe('function');
      expect(typeof client.getKnowledgeBase).toBe('function');
      expect(typeof client.updateKnowledgeBase).toBe('function');
      expect(typeof client.deleteKnowledgeBase).toBe('function');
      expect(typeof client.listKBDocuments).toBe('function');
      expect(typeof client.searchKnowledgeBase).toBe('function');
      expect(typeof client.reconcileKnowledgeBase).toBe('function');
      expect(typeof client.reconcileAllKnowledgeBases).toBe('function');
      // webhooks
      expect(typeof client.listWebhooks).toBe('function');
      expect(typeof client.createWebhook).toBe('function');
      expect(typeof client.getWebhook).toBe('function');
      expect(typeof client.updateWebhook).toBe('function');
      expect(typeof client.deleteWebhook).toBe('function');
      expect(typeof client.testWebhook).toBe('function');
      expect(typeof client.listWebhookDeliveries).toBe('function');
      expect(typeof client.getWebhookDelivery).toBe('function');
      expect(typeof client.retryWebhookDelivery).toBe('function');
    });

    test('uploadDocuments posts JSON to documents endpoint', async () => {
      const mockPost = jest.fn().mockResolvedValue({ documents: [] });
      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'org-token',
        organizationId: 'org-123',
      });
      (client as unknown as { http: { post: jest.Mock } }).http.post = mockPost;

      await client.uploadDocuments({
        documents: [{ name: 'x.pdf', content: 'Ym9keQ==' }],
      });
      expect(mockPost).toHaveBeenCalledWith('/v0/orgs/org-123/documents', {
        documents: [{ name: 'x.pdf', content: 'Ym9keQ==' }],
      });
    });

    test('uploadDocuments strips data URL prefix from content', async () => {
      const mockPost = jest.fn().mockResolvedValue({ documents: [] });
      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'org-token',
        organizationId: 'org-123',
      });
      (client as unknown as { http: { post: jest.Mock } }).http.post = mockPost;

      await client.uploadDocuments({
        documents: [
          {
            name: 'y.pdf',
            content: 'data:application/pdf;base64,Ym9keTI=',
          },
        ],
      });
      expect(mockPost).toHaveBeenCalledWith('/v0/orgs/org-123/documents', {
        documents: [{ name: 'y.pdf', content: 'Ym9keTI=' }],
      });
    });

    test('uploadDocumentsMultipart rejects empty documents', async () => {
      const mockPostFormData = jest.fn();
      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'org-token',
        organizationId: 'org-123',
      });
      (client as unknown as { http: { postFormData: jest.Mock } }).http.postFormData =
        mockPostFormData;

      await expect(
        client.uploadDocumentsMultipart({ documents: [] }),
      ).rejects.toThrow('uploadDocumentsMultipart requires at least one document');
      expect(mockPostFormData).not.toHaveBeenCalled();
    });

    test('uploadDocumentMultipart posts file, tag_ids and metadata as form fields', async () => {
      const mockPostFormData = jest.fn().mockResolvedValue({ document: { document_id: 'doc-1', document_name: 'one.pdf', upload_date: '', uploaded_by: '', state: '', tag_ids: [], metadata: {} } });
      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'org-token',
        organizationId: 'org-123',
      });
      (client as unknown as { http: { postFormData: jest.Mock } }).http.postFormData =
        mockPostFormData;

      const file = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
      await client.uploadDocumentMultipart({ name: 'one.pdf', file, tag_ids: ['tag_a'], metadata: { source: 'unit' } });

      expect(mockPostFormData).toHaveBeenCalledTimes(1);
      const [url, form] = mockPostFormData.mock.calls[0] as [string, FormData];
      expect(url).toBe('/v0/orgs/org-123/documents/multipart');
      expect(form.get('file')).toBeInstanceOf(Blob);
      expect(JSON.parse(form.get('tag_ids') as string)).toEqual(['tag_a']);
      expect(JSON.parse(form.get('metadata') as string)).toEqual({ source: 'unit' });
    });

    test('uploadDocumentsMultipart calls uploadDocumentMultipart once per file', async () => {
      const mockPostFormData = jest.fn().mockResolvedValue({ document: { document_id: 'doc-x', document_name: 'x.pdf', upload_date: '', uploaded_by: '', state: '', tag_ids: [], metadata: {} } });
      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'org-token',
        organizationId: 'org-99',
      });
      (client as unknown as { http: { postFormData: jest.Mock } }).http.postFormData =
        mockPostFormData;

      const a = new Blob(['a'], { type: 'application/pdf' });
      const b = new Blob(['b'], { type: 'application/pdf' });
      const result = await client.uploadDocumentsMultipart({
        documents: [
          { name: 'first.pdf', file: a },
          { name: 'second.pdf', file: b },
        ],
      });

      expect(mockPostFormData).toHaveBeenCalledTimes(2);
      expect(result.documents).toHaveLength(2);
    });

    test('getOCRBlocks accepts format param and requests gzip by default', async () => {
      const mockGet = jest.fn().mockResolvedValue([]);
      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'org-token',
        organizationId: 'org-123'
      });
      (client as unknown as { http: { get: jest.Mock } }).http.get = mockGet;

      await client.getOCRBlocks({ documentId: 'doc-456' });
      expect(mockGet).toHaveBeenCalledWith(
        '/v0/orgs/org-123/ocr/download/json/doc-456',
        { params: { format: 'gzip' } }
      );
    });

    test('getOCRBlocks can request plain format', async () => {
      const mockGet = jest.fn().mockResolvedValue([]);
      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'org-token',
        organizationId: 'org-123'
      });
      (client as unknown as { http: { get: jest.Mock } }).http.get = mockGet;

      await client.getOCRBlocks({ documentId: 'doc-789', format: 'plain' });
      expect(mockGet).toHaveBeenCalledWith(
        '/v0/orgs/org-123/ocr/download/json/doc-789',
        { params: { format: 'plain' } }
      );
    });

    test('getOCRBlocks unwraps Textract { Blocks } envelope to a flat array', async () => {
      const inner = [
        {
          Id: 'a',
          BlockType: 'WORD' as const,
          Confidence: 99,
          Page: 1,
          Text: 'hi',
          Geometry: {
            BoundingBox: { Left: 0.1, Top: 0.2, Width: 0.05, Height: 0.02 },
            Polygon: [],
          },
        },
      ];
      const mockGet = jest.fn().mockResolvedValue({ Blocks: inner });
      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'org-token',
        organizationId: 'org-123',
      });
      (client as unknown as { http: { get: jest.Mock } }).http.get = mockGet;

      const out = await client.getOCRBlocks({ documentId: 'doc-env' });
      expect(out).toEqual(inner);
    });

    test('should update org token', () => {
      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'initial-token',
        organizationId: 'org-123'
      });

      client.updateToken('new-token');
      expect(client).toBeDefined();
    });

    test('webhook endpoint methods call correct URLs', async () => {
      const mockGet = jest.fn();
      const mockPost = jest.fn();
      const mockPut = jest.fn();
      const mockDelete = jest.fn();

      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'org-token',
        organizationId: 'org-123'
      });

      (client as any).http = {
        get: mockGet,
        post: mockPost,
        put: mockPut,
        delete: mockDelete,
      };

      await client.listWebhooks();
      expect(mockGet).toHaveBeenCalledWith('/v0/orgs/org-123/webhooks');

      await client.createWebhook({ url: 'https://example.com/hook' });
      expect(mockPost).toHaveBeenCalledWith(
        '/v0/orgs/org-123/webhooks',
        expect.objectContaining({ url: 'https://example.com/hook' }),
      );

      await client.getWebhook('wh_1');
      expect(mockGet).toHaveBeenCalledWith('/v0/orgs/org-123/webhooks/wh_1');

      await client.updateWebhook({ webhookId: 'wh_1', enabled: false });
      expect(mockPut).toHaveBeenCalledWith(
        '/v0/orgs/org-123/webhooks/wh_1',
        expect.objectContaining({ enabled: false }),
      );

      await client.deleteWebhook('wh_1');
      expect(mockDelete).toHaveBeenCalledWith('/v0/orgs/org-123/webhooks/wh_1');

      await client.testWebhook('wh_1');
      expect(mockPost).toHaveBeenCalledWith(
        '/v0/orgs/org-123/webhooks/wh_1/test',
        {},
      );
    });

    test('webhook delivery methods call correct URLs and params', async () => {
      const mockGet = jest.fn();
      const mockPost = jest.fn();

      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'org-token',
        organizationId: 'org-123'
      });

      (client as any).http = {
        get: mockGet,
        post: mockPost,
      };

      await client.listWebhookDeliveries({
        status: 'failed',
        event_type: 'document.uploaded',
        webhook_id: 'wh_1',
        skip: 10,
        limit: 25,
      });
      expect(mockGet).toHaveBeenCalledWith(
        '/v0/orgs/org-123/webhooks/deliveries',
        {
          params: {
            status: 'failed',
            event_type: 'document.uploaded',
            webhook_id: 'wh_1',
            skip: 10,
            limit: 25,
          },
        },
      );

      await client.getWebhookDelivery('deliv_1');
      expect(mockGet).toHaveBeenCalledWith(
        '/v0/orgs/org-123/webhooks/deliveries/deliv_1',
      );

      await client.retryWebhookDelivery('deliv_1');
      expect(mockPost).toHaveBeenCalledWith(
        '/v0/orgs/org-123/webhooks/deliveries/deliv_1/retry',
        {},
      );
    });
  });

  describe('GetLLMResultResponse type', () => {
    test('accepts prompt_display_name for default prompt', () => {
      const response: GetLLMResultResponse = {
        prompt_revid: 'default',
        prompt_id: 'default',
        prompt_version: 1,
        document_id: 'doc-123',
        llm_result: { summary: 'test' },
        updated_llm_result: { summary: 'test' },
        is_edited: false,
        is_verified: false,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        prompt_display_name: 'Document Summary'
      };
      expect(response.prompt_display_name).toBe('Document Summary');
    });

    test('accepts response without prompt_display_name (non-default prompt)', () => {
      const response: GetLLMResultResponse = {
        prompt_revid: 'rev-456',
        prompt_id: 'prompt-id',
        prompt_version: 2,
        document_id: 'doc-123',
        llm_result: {},
        updated_llm_result: {},
        is_edited: false,
        is_verified: false,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z'
      };
      expect(response.prompt_display_name).toBeUndefined();
    });
  });
});
