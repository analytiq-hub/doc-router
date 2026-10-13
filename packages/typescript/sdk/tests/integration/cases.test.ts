import { DocRouterOrg } from '../../src';
import { getTestDatabase, getBaseUrl, createTestFixtures } from '../setup/jest-setup';

describe('Cases Integration Tests', () => {
  let testFixtures: Awaited<ReturnType<typeof createTestFixtures>>;
  let client: DocRouterOrg;

  function createMinimalPdfBase64(): string {
    const pdfContent = '%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n';
    return btoa(pdfContent);
  }

  beforeEach(async () => {
    const testDb = getTestDatabase();
    const baseUrl = getBaseUrl();
    testFixtures = await createTestFixtures(testDb, baseUrl);

    client = new DocRouterOrg({
      baseURL: baseUrl,
      orgToken: testFixtures.member.token,
      organizationId: testFixtures.org_id,
    });
  });

  test('create, get, list, update, delete case', async () => {
    const caseId = `SDK-CASE-${Date.now()}`;
    const created = await client.createCase({
      body: { case_id: caseId, display_name: 'SDK test case', metadata: { source: 'sdk-it' } },
    });
    expect(created.case_id).toBe(caseId);
    expect(created.metadata.source).toBe('sdk-it');

    const fetched = await client.getCase({ caseId });
    expect(fetched.display_name).toBe('SDK test case');

    const listed = await client.listCases({ caseIdSearch: caseId, limit: 10 });
    expect(listed.cases.some((c) => c.case_id === caseId)).toBe(true);

    const updated = await client.updateCase({
      caseId,
      body: { display_name: 'Updated SDK case' },
    });
    expect(updated.display_name).toBe('Updated SDK case');

    await client.deleteCase({ caseId, cascade: false });
    await expect(client.getCase({ caseId })).rejects.toThrow();
  });

  test('assign document via upload and list by case_id', async () => {
    const caseId = `SDK-DOC-${Date.now()}`;
    await client.createCase({ body: { case_id: caseId } });

    const upload = await client.uploadDocuments({
      documents: [
        {
          name: 'case-member.pdf',
          content: createMinimalPdfBase64(),
          case_id: caseId,
        },
      ],
    });
    expect(upload.documents[0].case_id).toBe(caseId);

    const listed = await client.listDocuments({ caseId, limit: 50 });
    expect(listed.documents.some((d) => d.case_id === caseId)).toBe(true);

    await client.deleteCase({ caseId, cascade: false });
  });
});
