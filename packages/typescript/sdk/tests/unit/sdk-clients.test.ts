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
      expect(typeof client.listDocuments).toBe('function');
      expect(typeof client.getDocument).toBe('function');
      expect(typeof client.updateDocument).toBe('function');
      expect(typeof client.deleteDocument).toBe('function');
      expect(typeof client.getOCRBlocks).toBe('function');
      expect(typeof client.getOCRText).toBe('function');
      expect(typeof client.getOCRMetadata).toBe('function');
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
        '/v0/orgs/org-123/ocr/download/blocks/doc-456',
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
        '/v0/orgs/org-123/ocr/download/blocks/doc-789',
        { params: { format: 'plain' } }
      );
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
