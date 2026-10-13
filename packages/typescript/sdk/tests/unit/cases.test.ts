import { DocRouterOrg } from '../../src';

function orgClient() {
  return new DocRouterOrg({
    baseURL: 'https://api.example.com',
    orgToken: 'org-token',
    organizationId: 'org-123',
  });
}

describe('Cases API unit tests', () => {
  test('DocRouterOrg exposes case methods', () => {
    const client = orgClient();
    expect(typeof client.listCases).toBe('function');
    expect(typeof client.getCase).toBe('function');
    expect(typeof client.createCase).toBe('function');
    expect(typeof client.updateCase).toBe('function');
    expect(typeof client.deleteCase).toBe('function');
    expect(typeof client.assignDocumentsToCase).toBe('function');
    expect(typeof client.removeDocumentFromCase).toBe('function');
  });

  test('listCases passes query params', async () => {
    const mockGet = jest.fn().mockResolvedValue({ cases: [], total_count: 0, skip: 0 });
    const client = orgClient();
    (client as unknown as { http: { get: jest.Mock } }).http.get = mockGet;

    await client.listCases({
      skip: 5,
      limit: 20,
      caseIdSearch: 'CLM',
      tagIds: 'tag1,tag2',
      metadataSearch: 'policy%3D123',
    });

    expect(mockGet).toHaveBeenCalledWith('/v0/orgs/org-123/cases', {
      params: {
        skip: 5,
        limit: 20,
        case_id_search: 'CLM',
        tag_ids: 'tag1,tag2',
        metadata_search: 'policy%3D123',
      },
    });
  });

  test('getCase encodes case id in path', async () => {
    const mockGet = jest.fn().mockResolvedValue({
      case_id: 'A:B',
      display_name: 'A:B',
      tag_ids: [],
      metadata: {},
      document_count: 0,
      created_by: 'u1',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });
    const client = orgClient();
    (client as unknown as { http: { get: jest.Mock } }).http.get = mockGet;

    await client.getCase({ caseId: 'A:B' });
    expect(mockGet).toHaveBeenCalledWith('/v0/orgs/org-123/cases/A%3AB');
  });

  test('createCase posts body', async () => {
    const mockPost = jest.fn().mockResolvedValue({
      case_id: 'CLM-1',
      display_name: 'CLM-1',
      tag_ids: [],
      metadata: {},
      document_count: 0,
      created_by: 'u1',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });
    const client = orgClient();
    (client as unknown as { http: { post: jest.Mock } }).http.post = mockPost;

    await client.createCase({
      body: { case_id: 'CLM-1', display_name: 'Claim', metadata: { region: 'US' } },
    });
    expect(mockPost).toHaveBeenCalledWith('/v0/orgs/org-123/cases', {
      case_id: 'CLM-1',
      display_name: 'Claim',
      metadata: { region: 'US' },
    });
  });

  test('updateCase puts to encoded path', async () => {
    const mockPut = jest.fn().mockResolvedValue({});
    const client = orgClient();
    (client as unknown as { http: { put: jest.Mock } }).http.put = mockPut;

    await client.updateCase({
      caseId: 'X/Y',
      body: { display_name: 'Updated' },
    });
    expect(mockPut).toHaveBeenCalledWith('/v0/orgs/org-123/cases/X%2FY', {
      display_name: 'Updated',
    });
  });

  test('deleteCase passes cascade query param', async () => {
    const mockDelete = jest.fn().mockResolvedValue({ message: 'Case delete started' });
    const client = orgClient();
    (client as unknown as { http: { delete: jest.Mock } }).http.delete = mockDelete;

    await client.deleteCase({ caseId: 'CLM-9', cascade: true });
    expect(mockDelete).toHaveBeenCalledWith('/v0/orgs/org-123/cases/CLM-9', {
      params: { cascade: true },
    });
  });

  test('assignDocumentsToCase posts document_ids', async () => {
    const mockPost = jest.fn().mockResolvedValue({ message: 'ok', count: 2 });
    const client = orgClient();
    (client as unknown as { http: { post: jest.Mock } }).http.post = mockPost;

    await client.assignDocumentsToCase({
      caseId: 'CLM-1',
      documentIds: ['d1', 'd2'],
      createCaseIfMissing: true,
    });
    expect(mockPost).toHaveBeenCalledWith('/v0/orgs/org-123/cases/CLM-1/documents', {
      document_ids: ['d1', 'd2'],
      create_case_if_missing: true,
    });
  });

  test('removeDocumentFromCase deletes document membership', async () => {
    const mockDelete = jest.fn().mockResolvedValue({ message: 'ok' });
    const client = orgClient();
    (client as unknown as { http: { delete: jest.Mock } }).http.delete = mockDelete;

    await client.removeDocumentFromCase({ caseId: 'CLM-1', documentId: 'doc-99' });
    expect(mockDelete).toHaveBeenCalledWith(
      '/v0/orgs/org-123/cases/CLM-1/documents/doc-99',
    );
  });
});

describe('Documents case fields unit tests', () => {
  test('uploadDocuments includes case_id and create_case_if_missing', async () => {
    const mockPost = jest.fn().mockResolvedValue({ documents: [] });
    const client = orgClient();
    (client as unknown as { http: { post: jest.Mock } }).http.post = mockPost;

    await client.uploadDocuments({
      documents: [
        {
          name: 'a.pdf',
          content: 'Ym9keQ==',
          case_id: 'CLM-1',
          create_case_if_missing: true,
        },
      ],
    });

    expect(mockPost).toHaveBeenCalledWith('/v0/orgs/org-123/documents', {
      documents: [
        {
          name: 'a.pdf',
          content: 'Ym9keQ==',
          case_id: 'CLM-1',
          create_case_if_missing: true,
        },
      ],
    });
  });

  test('uploadDocumentMultipart appends case form fields', async () => {
    const mockPostFormData = jest.fn().mockResolvedValue({
      document: {
        document_id: 'd1',
        document_name: 'a.pdf',
        upload_date: '',
        uploaded_by: '',
        state: '',
        tag_ids: [],
        metadata: {},
      },
    });
    const client = orgClient();
    (client as unknown as { http: { postFormData: jest.Mock } }).http.postFormData =
      mockPostFormData;

    const file = new Blob(['x'], { type: 'application/pdf' });
    await client.uploadDocumentMultipart({
      name: 'a.pdf',
      file,
      case_id: 'CLM-2',
      create_case_if_missing: true,
    });

    const [, form] = mockPostFormData.mock.calls[0] as [string, FormData];
    expect(form.get('case_id')).toBe('CLM-2');
    expect(form.get('create_case_if_missing')).toBe('true');
  });

  test('listDocuments passes case_id query param', async () => {
    const mockGet = jest.fn().mockResolvedValue({ documents: [], total_count: 0, skip: 0 });
    const client = orgClient();
    (client as unknown as { http: { get: jest.Mock } }).http.get = mockGet;

    await client.listDocuments({ caseId: 'CLM-3' });
    expect(mockGet).toHaveBeenCalledWith('/v0/orgs/org-123/documents', {
      params: expect.objectContaining({ case_id: 'CLM-3' }),
    });
  });

  test('updateDocument sends case_id null and create_case_if_missing', async () => {
    const mockPut = jest.fn().mockResolvedValue({});
    const client = orgClient();
    (client as unknown as { http: { put: jest.Mock } }).http.put = mockPut;

    await client.updateDocument({
      documentId: 'doc-1',
      caseId: null,
      createCaseIfMissing: false,
    });
    expect(mockPut).toHaveBeenCalledWith('/v0/orgs/org-123/documents/doc-1', {
      case_id: null,
      create_case_if_missing: false,
    });
  });
});
