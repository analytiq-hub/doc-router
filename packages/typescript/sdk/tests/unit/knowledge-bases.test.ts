import { DocRouterOrg } from '../../src';
import { HttpClient } from '../../src/http-client';

// Mock the HttpClient
jest.mock('../../src/http-client');
const MockedHttpClient = HttpClient as jest.MockedClass<typeof HttpClient>;

describe('DocRouterOrg Knowledge Bases Unit Tests', () => {
  let client: DocRouterOrg;
  let mockHttpClient: jest.Mocked<HttpClient>;
  const testOrgId = 'org-123';

  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks();
    
    // Create mock HTTP client
    mockHttpClient = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
      updateToken: jest.fn(),
    } as unknown as jest.Mocked<HttpClient>;

    // Mock the HttpClient constructor to return our mock
    MockedHttpClient.mockImplementation(() => mockHttpClient);

    // Create the client
    client = new DocRouterOrg({
      baseURL: 'https://api.example.com',
      orgToken: 'test-token',
      organizationId: testOrgId
    });
  });

  describe('createKnowledgeBase', () => {
    test('should call correct endpoint with KB config', async () => {
      const kbConfig = {
        name: 'Test KB',
        description: 'Test knowledge base',
        tag_ids: ['tag-1', 'tag-2'],
        chunker_type: 'recursive' as const,
        chunk_size: 512,
        chunk_overlap: 128,
        embedding_model: 'text-embedding-3-small',
        coalesce_neighbors: 2
      };

      const expectedResponse = {
        kb_id: 'kb-123',
        ...kbConfig,
        embedding_dimensions: 1536,
        status: 'active' as const,
        document_count: 0,
        chunk_count: 0,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z'
      };

      mockHttpClient.post.mockResolvedValue(expectedResponse);

      const result = await client.createKnowledgeBase({ kb: kbConfig });

      expect(mockHttpClient.post).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases`,
        kbConfig
      );
      expect(result).toEqual(expectedResponse);
    });

    test('should handle minimal KB config', async () => {
      const kbConfig = {
        name: 'Minimal KB'
      };

      const expectedResponse = {
        kb_id: 'kb-456',
        name: 'Minimal KB',
        description: '',
        tag_ids: [],
        chunker_type: 'recursive' as const,
        chunk_size: 512,
        chunk_overlap: 128,
        embedding_model: 'text-embedding-3-small',
        coalesce_neighbors: 0,
        embedding_dimensions: 1536,
        status: 'active' as const,
        document_count: 0,
        chunk_count: 0,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z'
      };

      mockHttpClient.post.mockResolvedValue(expectedResponse);

      const result = await client.createKnowledgeBase({ kb: kbConfig });

      expect(mockHttpClient.post).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases`,
        kbConfig
      );
      expect(result).toEqual(expectedResponse);
    });
  });

  describe('listKnowledgeBases', () => {
    test('should call endpoint without parameters', async () => {
      const expectedResponse = {
        knowledge_bases: [
          {
            kb_id: 'kb-123',
            name: 'Test KB',
            description: 'Test knowledge base',
            tag_ids: ['tag-1'],
            chunker_type: 'recursive' as const,
            chunk_size: 512,
            chunk_overlap: 128,
            embedding_model: 'text-embedding-3-small',
            coalesce_neighbors: 0,
            embedding_dimensions: 1536,
            status: 'active' as const,
            document_count: 5,
            chunk_count: 100,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z'
          }
        ],
        total_count: 1
      };

      mockHttpClient.get.mockResolvedValue(expectedResponse);

      const result = await client.listKnowledgeBases();

      expect(mockHttpClient.get).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases`,
        {
          params: {
            skip: 0,
            limit: 10,
            name_search: undefined
          }
        }
      );
      expect(result).toEqual(expectedResponse);
    });

    test('should call endpoint with pagination parameters', async () => {
      const params = { skip: 10, limit: 5 };
      const expectedResponse = {
        knowledge_bases: [],
        total_count: 0
      };

      mockHttpClient.get.mockResolvedValue(expectedResponse);

      const result = await client.listKnowledgeBases(params);

      expect(mockHttpClient.get).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases`,
        {
          params: {
            skip: 10,
            limit: 5,
            name_search: undefined
          }
        }
      );
      expect(result).toEqual(expectedResponse);
    });

    test('should call endpoint with name search', async () => {
      const params = { name_search: 'invoice' };
      const expectedResponse = {
        knowledge_bases: [
          {
            kb_id: 'kb-789',
            name: 'Invoice KB',
            description: 'Invoice knowledge base',
            tag_ids: [],
            chunker_type: 'recursive' as const,
            chunk_size: 512,
            chunk_overlap: 128,
            embedding_model: 'text-embedding-3-small',
            coalesce_neighbors: 0,
            embedding_dimensions: 1536,
            status: 'active' as const,
            document_count: 10,
            chunk_count: 200,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z'
          }
        ],
        total_count: 1
      };

      mockHttpClient.get.mockResolvedValue(expectedResponse);

      const result = await client.listKnowledgeBases(params);

      expect(mockHttpClient.get).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases`,
        {
          params: {
            skip: 0,
            limit: 10,
            name_search: 'invoice'
          }
        }
      );
      expect(result).toEqual(expectedResponse);
    });
  });

  describe('getKnowledgeBase', () => {
    test('should call endpoint with KB ID', async () => {
      const kbId = 'kb-123';
      const expectedResponse = {
        kb_id: kbId,
        name: 'Test KB',
        description: 'Test knowledge base',
        tag_ids: ['tag-1'],
        chunker_type: 'recursive' as const,
        chunk_size: 512,
        chunk_overlap: 128,
        embedding_model: 'text-embedding-3-small',
        coalesce_neighbors: 2,
        embedding_dimensions: 1536,
        status: 'active' as const,
        document_count: 5,
        chunk_count: 100,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z'
      };

      mockHttpClient.get.mockResolvedValue(expectedResponse);

      const result = await client.getKnowledgeBase({ kbId });

      expect(mockHttpClient.get).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases/${kbId}`
      );
      expect(result).toEqual(expectedResponse);
    });
  });

  describe('updateKnowledgeBase', () => {
    test('should call endpoint with KB ID and update data', async () => {
      const kbId = 'kb-123';
      const update = {
        name: 'Updated KB Name',
        description: 'Updated description',
        tag_ids: ['tag-1', 'tag-3'],
        coalesce_neighbors: 3
      };

      const expectedResponse = {
        kb_id: kbId,
        name: 'Updated KB Name',
        description: 'Updated description',
        tag_ids: ['tag-1', 'tag-3'],
        chunker_type: 'recursive' as const,
        chunk_size: 512,
        chunk_overlap: 128,
        embedding_model: 'text-embedding-3-small',
        coalesce_neighbors: 3,
        embedding_dimensions: 1536,
        status: 'active' as const,
        document_count: 5,
        chunk_count: 100,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z'
      };

      mockHttpClient.put.mockResolvedValue(expectedResponse);

      const result = await client.updateKnowledgeBase({ kbId, update });

      expect(mockHttpClient.put).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases/${kbId}`,
        update
      );
      expect(result).toEqual(expectedResponse);
    });

    test('should handle partial update', async () => {
      const kbId = 'kb-123';
      const update = {
        name: 'Partially Updated KB'
      };

      const expectedResponse = {
        kb_id: kbId,
        name: 'Partially Updated KB',
        description: 'Original description',
        tag_ids: ['tag-1'],
        chunker_type: 'recursive' as const,
        chunk_size: 512,
        chunk_overlap: 128,
        embedding_model: 'text-embedding-3-small',
        coalesce_neighbors: 0,
        embedding_dimensions: 1536,
        status: 'active' as const,
        document_count: 5,
        chunk_count: 100,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z'
      };

      mockHttpClient.put.mockResolvedValue(expectedResponse);

      const result = await client.updateKnowledgeBase({ kbId, update });

      expect(mockHttpClient.put).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases/${kbId}`,
        update
      );
      expect(result).toEqual(expectedResponse);
    });
  });

  describe('deleteKnowledgeBase', () => {
    test('should call endpoint with KB ID', async () => {
      const kbId = 'kb-123';
      const expectedResponse = {
        message: 'Knowledge base deleted successfully'
      };

      mockHttpClient.delete.mockResolvedValue(expectedResponse);

      const result = await client.deleteKnowledgeBase({ kbId });

      expect(mockHttpClient.delete).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases/${kbId}`
      );
      expect(result).toEqual(expectedResponse);
    });
  });

  describe('listKBDocuments', () => {
    test('should call endpoint without parameters', async () => {
      const kbId = 'kb-123';
      const expectedResponse = {
        documents: [
          {
            document_id: 'doc-1',
            document_name: 'test.pdf',
            chunk_count: 10,
            indexed_at: '2024-01-01T00:00:00Z'
          },
          {
            document_id: 'doc-2',
            document_name: 'test2.pdf',
            chunk_count: 15,
            indexed_at: '2024-01-02T00:00:00Z'
          }
        ],
        total_count: 2
      };

      mockHttpClient.get.mockResolvedValue(expectedResponse);

      const result = await client.listKBDocuments({ kbId });

      expect(mockHttpClient.get).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases/${kbId}/documents`,
        {
          params: {
            skip: 0,
            limit: 10
          }
        }
      );
      expect(result).toEqual(expectedResponse);
    });

    test('should call endpoint with pagination parameters', async () => {
      const kbId = 'kb-123';
      const params = { kbId, skip: 5, limit: 20 };
      const expectedResponse = {
        documents: [],
        total_count: 0
      };

      mockHttpClient.get.mockResolvedValue(expectedResponse);

      const result = await client.listKBDocuments(params);

      expect(mockHttpClient.get).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases/${kbId}/documents`,
        {
          params: {
            skip: 5,
            limit: 20
          }
        }
      );
      expect(result).toEqual(expectedResponse);
    });
  });

  describe('searchKnowledgeBase', () => {
    test('should call endpoint with search query', async () => {
      const kbId = 'kb-123';
      const search = {
        query: 'What are the payment terms?',
        top_k: 5
      };

      const expectedResponse = {
        results: [
          {
            content: 'Payment is due within 30 days of invoice date...',
            source: 'invoice-2024-001.pdf',
            document_id: 'doc-1',
            relevance: 0.92,
            chunk_index: 5,
            is_matched: true
          },
          {
            content: 'Payment terms are net 30...',
            source: 'invoice-2024-002.pdf',
            document_id: 'doc-2',
            relevance: 0.85,
            chunk_index: 3,
            is_matched: true
          }
        ],
        query: 'What are the payment terms?',
        total_count: 2,
        skip: 0,
        top_k: 5
      };

      mockHttpClient.post.mockResolvedValue(expectedResponse);

      const result = await client.searchKnowledgeBase({ kbId, search });

      expect(mockHttpClient.post).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases/${kbId}/search`,
        search
      );
      expect(result).toEqual(expectedResponse);
    });

    test('should call endpoint with full search parameters', async () => {
      const kbId = 'kb-123';
      const search = {
        query: 'invoice details',
        top_k: 10,
        skip: 5,
        document_ids: ['doc-1', 'doc-2'],
        metadata_filter: {
          document_name: 'invoice'
        },
        upload_date_from: '2024-01-01T00:00:00Z',
        upload_date_to: '2024-12-31T23:59:59Z',
        coalesce_neighbors: 2
      };

      const expectedResponse = {
        results: [],
        query: 'invoice details',
        total_count: 0,
        skip: 5,
        top_k: 10
      };

      mockHttpClient.post.mockResolvedValue(expectedResponse);

      const result = await client.searchKnowledgeBase({ kbId, search });

      expect(mockHttpClient.post).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases/${kbId}/search`,
        search
      );
      expect(result).toEqual(expectedResponse);
    });
  });

  describe('reconcileKnowledgeBase', () => {
    test('should call endpoint without dry_run parameter', async () => {
      const kbId = 'kb-123';
      const expectedResponse = {
        kb_id: kbId,
        missing_documents: ['doc-1', 'doc-2'],
        stale_documents: ['doc-3'],
        orphaned_vectors: 5,
        missing_embeddings: 0,
        dry_run: false
      };

      mockHttpClient.post.mockResolvedValue(expectedResponse);

      const result = await client.reconcileKnowledgeBase({ kbId });

      expect(mockHttpClient.post).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases/${kbId}/reconcile`,
        {},
        {
          params: { dry_run: false }
        }
      );
      expect(result).toEqual(expectedResponse);
    });

    test('should call endpoint with dry_run=true', async () => {
      const kbId = 'kb-123';
      const expectedResponse = {
        kb_id: kbId,
        missing_documents: ['doc-1', 'doc-2'],
        stale_documents: ['doc-3'],
        orphaned_vectors: 5,
        missing_embeddings: 0,
        dry_run: true
      };

      mockHttpClient.post.mockResolvedValue(expectedResponse);

      const result = await client.reconcileKnowledgeBase({ kbId, dry_run: true });

      expect(mockHttpClient.post).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases/${kbId}/reconcile`,
        {},
        {
          params: { dry_run: true }
        }
      );
      expect(result).toEqual(expectedResponse);
    });
  });

  describe('reconcileAllKnowledgeBases', () => {
    test('should call endpoint without dry_run parameter', async () => {
      const expectedResponse = {
        kb_results: [
          {
            kb_id: 'kb-1',
            missing_documents: ['doc-1'],
            stale_documents: [],
            orphaned_vectors: 0,
            missing_embeddings: 0,
            dry_run: false
          },
          {
            kb_id: 'kb-2',
            missing_documents: [],
            stale_documents: ['doc-2'],
            orphaned_vectors: 2,
            missing_embeddings: 0,
            dry_run: false
          }
        ],
        total_missing: 1,
        total_stale: 1,
        total_orphaned: 2,
        dry_run: false
      };

      mockHttpClient.post.mockResolvedValue(expectedResponse);

      const result = await client.reconcileAllKnowledgeBases();

      expect(mockHttpClient.post).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases/reconcile-all`,
        {},
        {
          params: { dry_run: false }
        }
      );
      expect(result).toEqual(expectedResponse);
    });

    test('should call endpoint with dry_run=true', async () => {
      const expectedResponse = {
        kb_results: [
          {
            kb_id: 'kb-1',
            missing_documents: ['doc-1'],
            stale_documents: [],
            orphaned_vectors: 0,
            missing_embeddings: 0,
            dry_run: true
          }
        ],
        total_missing: 1,
        total_stale: 0,
        total_orphaned: 0,
        dry_run: true
      };

      mockHttpClient.post.mockResolvedValue(expectedResponse);

      const result = await client.reconcileAllKnowledgeBases({ dry_run: true });

      expect(mockHttpClient.post).toHaveBeenCalledWith(
        `/v0/orgs/${testOrgId}/knowledge-bases/reconcile-all`,
        {},
        {
          params: { dry_run: true }
        }
      );
      expect(result).toEqual(expectedResponse);
    });
  });
});
