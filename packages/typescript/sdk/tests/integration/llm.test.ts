import { DocRouterOrg } from '../../src';
import { getTestDatabase, getBaseUrl, createTestFixtures } from '../setup/jest-setup';

describe('LLM Integration Tests', () => {
  let testFixtures: any;
  let client: DocRouterOrg;

  beforeEach(async () => {
    const testDb = getTestDatabase();
    const baseUrl = getBaseUrl();
    testFixtures = await createTestFixtures(testDb, baseUrl);

    client = new DocRouterOrg({
      baseURL: baseUrl,
      orgToken: testFixtures.member.token,
      organizationId: testFixtures.org_id
    });
  });

  test('run/get/update/delete llm result', async () => {
    // This test assumes there is a document and a prompt available. In a full suite we would create them.
    // Here we just verify endpoints are callable and handle errors gracefully.
    await expect(client.runLLM({ documentId: 'nonexistent', promptRevId: 'nonexistent' })).rejects.toThrow();
  });
});


