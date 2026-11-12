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
    const caseName = `SDK-CASE-${Date.now()}`;
    const created = await client.createCase({
      body: { name: caseName, metadata: { source: 'sdk-it' } },
    });
    const caseId = created.case_id;
    expect(caseId).toMatch(/^[0-9a-f]{24}$/i);
    expect(created.metadata.source).toBe('sdk-it');

    const fetched = await client.getCase({ caseId });
    expect(fetched.name).toBe(caseName);

    const listed = await client.listCases({ caseIdSearch: caseName, limit: 10 });
    expect(listed.cases.some((c) => c.case_id === caseId)).toBe(true);

    const updated = await client.updateCase({
      caseId,
      body: { name: 'Updated SDK case' },
    });
    expect(updated.name).toBe('Updated SDK case');

    await client.deleteCase({ caseId, cascade: false });
    await expect(client.getCase({ caseId })).rejects.toThrow();
  });

  test('assign document via upload and list by case_id', async () => {
    const created = await client.createCase({ body: { name: `SDK-DOC-${Date.now()}` } });
    const caseId = created.case_id;

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
