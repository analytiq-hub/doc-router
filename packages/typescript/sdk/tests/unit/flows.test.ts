import { DocRouterOrg } from '../../src';

describe('Flows SDK Unit Tests', () => {
  test('listFlowNodeTypes hits flows node-types endpoint', async () => {
    const mockGet = jest.fn().mockResolvedValue({ items: [], total: 0 });
    const client = new DocRouterOrg({
      baseURL: 'https://api.example.com',
      orgToken: 'org-token',
      organizationId: 'org-123',
    });
    (client as unknown as { http: { get: jest.Mock } }).http.get = mockGet;

    await client.listFlowNodeTypes();
    expect(mockGet).toHaveBeenCalledWith('/v0/orgs/org-123/flows/node-types');
  });

  test('createFlow posts JSON to flows endpoint', async () => {
    const mockPost = jest.fn().mockResolvedValue({ flow: { flow_id: 'f1' } });
    const client = new DocRouterOrg({
      baseURL: 'https://api.example.com',
      orgToken: 'org-token',
      organizationId: 'org-123',
    });
    (client as unknown as { http: { post: jest.Mock } }).http.post = mockPost;

    await client.createFlow({ name: 'My flow' });
    expect(mockPost).toHaveBeenCalledWith('/v0/orgs/org-123/flows', { name: 'My flow' });
  });

  test('deleteFlow calls DELETE on flows/{id}', async () => {
    const mockDelete = jest.fn().mockResolvedValue(undefined);
    const client = new DocRouterOrg({
      baseURL: 'https://api.example.com',
      orgToken: 'org-token',
      organizationId: 'org-123',
    });
    (client as unknown as { http: { delete: jest.Mock } }).http.delete = mockDelete;

    await client.deleteFlow('flow-1');
    expect(mockDelete).toHaveBeenCalledWith('/v0/orgs/org-123/flows/flow-1');
  });
});

