// frontend/src/types/tables.ts
export interface TableColumn {
  key: string;
  name: string;
  width?: number;
  editable?: boolean;
  [key: string]: unknown;
}

export interface TableResponseFormat {
  columns?: TableColumn[] | null;
  row_schema?: Record<string, unknown> | null;
  // Reuse Form FieldMapping shape for table column mapping
  column_mapping?: Record<string, import('./forms').FieldMapping>;
}

export interface Table {
  table_revid: string; // MongoDB's _id
  table_id: string;    // Stable identifier
  name: string;
  response_format: TableResponseFormat;
  table_version: number;
  created_at: string;
  created_by: string;
  tag_ids?: string[];
}

export interface TableConfig {
  name: string;
  response_format: TableResponseFormat;
  tag_ids?: string[];
}

export interface CreateTableParams extends TableConfig {
  organizationId: string;
}

export interface ListTablesParams {
  organizationId: string;
  skip?: number;
  limit?: number;
  tag_ids?: string;
}

export interface ListTablesResponse {
  tables: Table[];
  total_count: number;
  skip: number;
}

export interface GetTableParams {
  organizationId: string;
  tableRevId: string;
}

export interface UpdateTableParams {
  organizationId: string;
  tableId: string;
  table: TableConfig;
}

export interface DeleteTableParams {
  organizationId: string;
  tableId: string;
}

export interface TableSubmissionData {
  table_revid: string;
  submission_data: Array<Record<string, unknown>>; // rows payload
  submitted_by?: string;
}

export interface TableSubmission extends TableSubmissionData {
  id: string;
  organization_id: string;
  created_at: string;
  updated_at: string;
}

export interface SubmitTableParams {
  organizationId: string;
  documentId: string;
  submission: TableSubmissionData;
}

export interface GetTableSubmissionParams {
  organizationId: string;
  documentId: string;
  tableRevId: string;
}

export interface DeleteTableSubmissionParams {
  organizationId: string;
  documentId: string;
  tableRevId: string;
}
