import { DocRouterAccount, DocRouterOrg } from '../../src';

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
});
