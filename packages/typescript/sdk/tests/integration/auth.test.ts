import { DocRouterAccount, DocRouterOrg } from '../../src';
import { getTestDatabase, getBaseUrl, createTestFixtures } from '../setup/jest-setup';

describe('Authentication Integration Tests', () => {
  let testFixtures: any;

  beforeEach(async () => {
    const testDb = getTestDatabase();
    const baseUrl = getBaseUrl();

    // Create test users and tokens
    testFixtures = await createTestFixtures(testDb, baseUrl);
  });

  // DocRouter removed

  describe('DocRouterAccount (Account-level)', () => {
    test('should authenticate with account token', async () => {
      const client = new DocRouterAccount({
        baseURL: getBaseUrl(),
        accountToken: testFixtures.admin.account_token
      });

      const orgs = await client.listOrganizations();
      expect(orgs).toBeDefined();
      expect(Array.isArray(orgs.organizations)).toBe(true);
    });

    test('should create organization tokens', async () => {
      const client = new DocRouterAccount({
        baseURL: getBaseUrl(),
        accountToken: testFixtures.admin.account_token
      });

      const token: any = await client.createOrganizationToken({
        name: 'Test Org Token',
        lifetime: 86400
      }, testFixtures.org_id);

      expect(token).toBeDefined();
      expect(token.name).toBe('Test Org Token');
    });

    test('should list account tokens', async () => {
      const client = new DocRouterAccount({
        baseURL: getBaseUrl(),
        accountToken: testFixtures.admin.account_token
      });

      const accountTokens = await client.getAccountTokens();
      expect(accountTokens).toBeDefined();
      expect(Array.isArray(accountTokens)).toBe(true);
    });
  });

  describe('DocRouterOrg (Organization-scoped)', () => {
    test('should authenticate with org token', async () => {
      const client = new DocRouterOrg({
        baseURL: getBaseUrl(),
        orgToken: testFixtures.member.token,
        organizationId: testFixtures.org_id
      });

      // Test organization-scoped endpoint
      const documents = await client.listDocuments();
      expect(documents).toBeDefined();
    });

    test('should handle invalid org token', async () => {
      const client = new DocRouterOrg({
        baseURL: getBaseUrl(),
        orgToken: 'invalid_token',
        organizationId: testFixtures.org_id,
        onAuthError: (error) => {
          expect(error.message).toContain('authentication');
        }
      });

      await expect(client.listDocuments()).rejects.toThrow();
    });

    test('should update token', async () => {
      const client = new DocRouterOrg({
        baseURL: getBaseUrl(),
        orgToken: testFixtures.member.token,
        organizationId: testFixtures.org_id
      });

      // Update with a different member token (should be the same in this case)
      client.updateToken(testFixtures.member.token);
      
      // Should still work with new token
      const documents = await client.listDocuments();
      expect(documents).toBeDefined();
    });
  });

  describe('Permission Tests', () => {
    test('org admin (member) should have full access', async () => {
      const client = new DocRouterOrg({
        baseURL: getBaseUrl(),
        orgToken: testFixtures.member.token,
        organizationId: testFixtures.org_id
      });

      // Org admin should be able to list documents
      const documents = await client.listDocuments();
      expect(documents).toBeDefined();
    });

    test('outsider should not have access', async () => {
      const client = new DocRouterOrg({
        baseURL: getBaseUrl(),
        orgToken: testFixtures.outsider.token,
        organizationId: testFixtures.org_id,
        onAuthError: (error) => {
          expect(error.message).toContain('access');
        }
      });

      // Outsider should not be able to access org resources
      await expect(client.listDocuments()).rejects.toThrow();
    });
  });
});
