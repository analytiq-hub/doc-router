export interface DocumentWithContent {
  name: string;
  content: string; // Base64 encoded content (can be data URL or plain base64)
  tag_ids?: string[];  // Optional list of tag IDs
  metadata?: Record<string, string>;  // Optional key-value metadata pairs
}

export interface UploadDocumentsParams {
  organizationId: string;
  documents: DocumentWithContent[];
}

export interface UploadDocumentsResponse {
  documents: Array<{
    document_name: string;
    document_id: string;
    tag_ids?: string[];
    metadata?: Record<string, string>;
  }>;
}

export interface UploadedDocument {
    document_name: string;
    document_id: string;
}

export interface DocumentMetadata {
    id: string;
    pdf_id: string;
    document_name: string;
    upload_date: string;
    uploaded_by: string;
    state: string;
    tag_ids: string[];  // List of tag IDs
    type?: string;      // MIME type of the returned file
    metadata?: Record<string, string>;  // Optional key-value metadata pairs
}

export interface ListDocumentsResponse {
    documents: DocumentMetadata[];
    total_count: number;
    skip: number;
}

export interface ListDocumentsParams {
  organizationId: string;
  skip?: number;
  limit?: number;
  tagIds?: string;  // Comma-separated list of tag IDs
  nameSearch?: string;  // Search term for document names
  metadataSearch?: string;  // Metadata search as key=value pairs, comma-separated
}

export interface GetDocumentParams {
  organizationId: string;
  documentId: string;
  fileType?: string; // "original" or "pdf". Default is "original".
}

export interface GetDocumentResponse {
  id: string;
  pdf_id: string;
  document_name: string;
  upload_date: string;
  uploaded_by: string;
  state: string;
  tag_ids: string[];
  type?: string;
  metadata?: Record<string, string>;
  content: ArrayBuffer;
}

export interface UpdateDocumentParams {
  organizationId: string;
  documentId: string;
  documentName?: string;
  tagIds?: string[];
  metadata?: Record<string, string>;
}

export interface DeleteDocumentParams {
  organizationId: string;
  documentId: string;
}