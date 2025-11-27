import { DocRouterOrg } from '../../src';
import { getTestDatabase, getBaseUrl, createTestFixtures } from '../setup/jest-setup';

describe('Documents Integration Tests', () => {
  let testFixtures: { org_id: string; admin: { id: string; token: string; account_token: string }; member: { id: string; token: string; account_token: string }; outsider: { id: string; token: string; account_token: string } };
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

  // Helper to create a minimal PDF as base64
  function createMinimalPdfBase64(): string {
    const pdfContent = "%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n";
    return btoa(pdfContent);
  }

  describe('upload', () => {
    test('should upload a document', async () => {
      const response = await client.uploadDocuments({
        documents: [{
          name: 'test.pdf',
          content: createMinimalPdfBase64()
        }]
      });

      expect(response.documents).toBeDefined();
      expect(response.documents.length).toBe(1);
      expect(response.documents[0].document_name).toBe('test.pdf');
    });

    test('should upload document with metadata', async () => {
      const metadata = { author: 'Test User', department: 'Testing' };

      const response = await client.uploadDocuments({
        documents: [{
          name: 'test-metadata.pdf',
          content: createMinimalPdfBase64(),
          metadata
        }]
      });

      expect(response.documents[0].metadata).toEqual(metadata);
    });

    test('should upload multiple documents', async () => {
      const response = await client.uploadDocuments({
        documents: [
          { name: 'test1.pdf', content: createMinimalPdfBase64() },
          { name: 'test2.pdf', content: createMinimalPdfBase64() }
        ]
      });

      expect(response.documents.length).toBe(2);
    });

    test('should upload document with tag_ids', async () => {
      // First create a tag
      const tagResponse = await client.createTag({
        tag: {
          name: 'Test Tag',
          color: '#FF0000'
        }
      });

      const response = await client.uploadDocuments({
        documents: [{
          name: 'test-tags.pdf',
          content: createMinimalPdfBase64(),
          tag_ids: [tagResponse.id]
        }]
      });

      expect(response.documents[0].tag_ids).toContain(tagResponse.id);
    });

    test('should upload document with data URL content', async () => {
      const dataUrl = `data:application/pdf;base64,${createMinimalPdfBase64()}`;
      
      const response = await client.uploadDocuments({
        documents: [{
          name: 'test-dataurl.pdf',
          content: dataUrl
        }]
      });

      expect(response.documents).toBeDefined();
      expect(response.documents.length).toBe(1);
      expect(response.documents[0].document_name).toBe('test-dataurl.pdf');
    });
  });

  describe('list', () => {
    test('should list documents', async () => {
      const response = await client.listDocuments();

      expect(response.documents).toBeDefined();
      expect(Array.isArray(response.documents)).toBe(true);
    });

    test('should list documents with skip parameter', async () => {
      const response = await client.listDocuments({
        skip: 0
      });

      expect(response.skip).toBe(0);
    });

    test('should list documents with limit parameter', async () => {
      const response = await client.listDocuments({
        limit: 5
      });

      expect(response.documents.length).toBeLessThanOrEqual(5);
    });

    test('should list documents with nameSearch parameter', async () => {
      // Upload a document first
      await client.uploadDocuments({
        documents: [{
          name: 'searchable-document.pdf',
          content: createMinimalPdfBase64(),
        }]
      });

      const response = await client.listDocuments({
        nameSearch: 'searchable'
      });

      expect(response.documents.length).toBeGreaterThan(0);
      expect(response.documents[0].document_name).toContain('searchable');
    });

    test('should list documents with metadataSearch parameter', async () => {
      // Upload a document with metadata
      await client.uploadDocuments({
        documents: [{
          name: 'metadata-doc.pdf',
          content: createMinimalPdfBase64(),
          metadata: { type: 'invoice' }
        }]
      });

      const response = await client.listDocuments({
        metadataSearch: 'type=invoice'
      });

      expect(response.documents.length).toBeGreaterThan(0);
    });

    test('should list documents with tagIds parameter', async () => {
      // Create a tag first
      const tagResponse = await client.createTag({
        tag: {
          name: 'Test Tag',
          color: '#FF0000'
        }
      });
      const tagId = tagResponse.id;

      // Upload a document with the tag
      const uploadResponse = await client.uploadDocuments({
        documents: [{
          name: 'tagged-doc.pdf',
          content: createMinimalPdfBase64(),
        }]
      });
      const docId = uploadResponse.documents[0].document_id;

      // Update document with tag
      await client.updateDocument({
        documentId: docId,
        tagIds: [tagId]
      });

      // List with tag filter
      const response = await client.listDocuments({
        tagIds: tagId
      });

      expect(response.documents.length).toBeGreaterThan(0);
      const taggedDoc = response.documents.find(d => d.id === docId);
      expect(taggedDoc?.tag_ids).toContain(tagId);
    });
  });

  describe('get', () => {
    test('should get document by id', async () => {
      // Upload a document first
      const uploadResponse = await client.uploadDocuments({
        documents: [{
          name: 'get-test.pdf',
          content: createMinimalPdfBase64(),
        }]
      });
      const docId = uploadResponse.documents[0].document_id;

      const response = await client.getDocument({
        documentId: docId,
        fileType: 'original'
      });

      expect(response.id).toBe(docId);
      expect(response.document_name).toBe('get-test.pdf');
      expect(response.content).toBeDefined();
    });

    test('should get document with fileType=pdf parameter', async () => {
      // Upload a document first
      const uploadResponse = await client.uploadDocuments({
        documents: [{
          name: 'pdf-type-test.pdf',
          content: createMinimalPdfBase64(),
        }]
      });
      const docId = uploadResponse.documents[0].document_id;

      const response = await client.getDocument({
        documentId: docId,
        fileType: 'pdf'
      });

      expect(response.id).toBe(docId);
      expect(response.content).toBeDefined();
    });
  });

  describe('update', () => {
    test('should update document name', async () => {
      // Upload a document first
      const uploadResponse = await client.uploadDocuments({
        documents: [{
          name: 'original-name.pdf',
          content: createMinimalPdfBase64(),
        }]
      });
      const docId = uploadResponse.documents[0].document_id;

      await client.updateDocument({
        documentId: docId,
        documentName: 'updated-name.pdf'
      });

      const response = await client.getDocument({
        documentId: docId,
        fileType: 'original'
      });

      expect(response.document_name).toBe('updated-name.pdf');
    });

    test('should update document tagIds', async () => {
      // Create a tag
      const tagResponse = await client.createTag({
        tag: {
          name: 'Update Tag',
          color: '#00FF00'
        }
      });
      const tagId = tagResponse.id;

      // Upload a document
      const uploadResponse = await client.uploadDocuments({
        documents: [{
          name: 'tag-update-test.pdf',
          content: createMinimalPdfBase64(),
        }]
      });
      const docId = uploadResponse.documents[0].document_id;

      // Update with tag
      await client.updateDocument({
        documentId: docId,
        tagIds: [tagId]
      });

      const response = await client.getDocument({
        documentId: docId,
        fileType: 'original'
      });

      expect(response.tag_ids).toContain(tagId);
    });

    test('should update document metadata', async () => {
      // Upload a document
      const uploadResponse = await client.uploadDocuments({
        documents: [{
          name: 'metadata-update-test.pdf',
          content: createMinimalPdfBase64(),
        }]
      });
      const docId = uploadResponse.documents[0].document_id;

      const newMetadata = { status: 'reviewed', reviewer: 'Admin' };

      // Update metadata
      await client.updateDocument({
        documentId: docId,
        metadata: newMetadata
      });

      const response = await client.getDocument({
        documentId: docId,
        fileType: 'original'
      });

      expect(response.metadata).toEqual(newMetadata);
    });
  });

  describe('delete', () => {
    test('should delete document', async () => {
      // Upload a document first
      const uploadResponse = await client.uploadDocuments({
        documents: [{
          name: 'delete-test.pdf',
          content: createMinimalPdfBase64(),
        }]
      });
      const docId = uploadResponse.documents[0].document_id;

      // Delete the document
      await client.deleteDocument({
        documentId: docId
      });

      // Verify it's deleted
      await expect(client.getDocument({
        documentId: docId,
        fileType: 'original'
      })).rejects.toThrow();
    });
  });
});
