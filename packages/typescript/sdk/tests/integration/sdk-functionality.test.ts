import { DocRouterAccount, DocRouterOrg } from '../../src';

describe('SDK Functionality Tests', () => {
  describe('Client Instantiation', () => {
    test('DocRouterAccount should be constructible', () => {
      const client = new DocRouterAccount({
        baseURL: 'https://api.example.com',
        accountToken: 'test-token'
      });
      expect(client).toBeDefined();
    });

    test('DocRouterAccount should expose account-level APIs', () => {
      const client = new DocRouterAccount({
        baseURL: 'https://api.example.com',
        accountToken: 'account-token'
      });

      expect(typeof client.listOrganizations).toBe('function');
      expect(typeof client.createOrganization).toBe('function');
      expect(typeof client.listLLMModels).toBe('function');
      expect(typeof client.listLLMProviders).toBe('function');
      expect(typeof client.createAccountToken).toBe('function');
      expect(typeof client.listUsers).toBe('function');
    });

    test('DocRouterOrg should create organization-scoped API modules', () => {
      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'org-token',
        organizationId: 'org-123'
      });

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
  });

  describe('Token Management', () => {
    // DocRouter removed

    test('should update tokens on DocRouterAccount', () => {
      const client = new DocRouterAccount({
        baseURL: 'https://api.example.com',
        accountToken: 'initial-token'
      });

      client.updateToken('new-token');
      expect(client).toBeDefined();
    });

    test('should update tokens on DocRouterOrg', () => {
      const client = new DocRouterOrg({
        baseURL: 'https://api.example.com',
        orgToken: 'initial-token',
        organizationId: 'org-123'
      });

      client.updateToken('new-token');
      expect(client).toBeDefined();
    });

    // DocRouter removed
  });

  describe('API Module Methods', () => {
    test('DocRouterAccount organizations methods should exist', () => {
      const client = new DocRouterAccount({
        baseURL: 'https://api.example.com',
        accountToken: 'test-token'
      });
      expect(typeof client.listOrganizations).toBe('function');
      expect(typeof client.getOrganization).toBe('function');
      expect(typeof client.createOrganization).toBe('function');
      expect(typeof client.updateOrganization).toBe('function');
      expect(typeof client.deleteOrganization).toBe('function');
    });

    // DocRouter removed

    // DocRouter removed

    test('account token methods should exist', () => {
      const client = new DocRouterAccount({
        baseURL: 'https://api.example.com',
        accountToken: 'test-token'
      });

      expect(typeof client.getAccountTokens).toBe('function');
      expect(typeof client.createOrganizationToken).toBe('function');
      expect(typeof client.deleteAccountToken).toBe('function');
      expect(typeof client.deleteOrganizationToken).toBe('function');
    });

    test('account user methods should exist', () => {
      const client = new DocRouterAccount({
        baseURL: 'https://api.example.com',
        accountToken: 'test-token'
      });

      expect(typeof client.listUsers).toBe('function');
      expect(typeof client.getUser).toBe('function');
      expect(typeof client.createUser).toBe('function');
      expect(typeof client.updateUser).toBe('function');
      expect(typeof client.deleteUser).toBe('function');
    });
  });

  describe('Configuration', () => {
    // DocRouter removed

    // DocRouter removed

    // DocRouter removed
  });
});
