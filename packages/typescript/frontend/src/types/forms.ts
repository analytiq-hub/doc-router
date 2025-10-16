export interface FormResponseFormat {
  json_formio?: object | null; // Just use any for the free-form dict
  json_formio_mapping?: Record<string, FieldMapping>; // Field mappings from schema to form fields
}

export interface Form {
  form_revid: string; // MongoDB's _id
  form_id: string;  // Stable identifier
  name: string;
  response_format: FormResponseFormat;
  form_version: number;
  created_at: string;
  created_by: string;
  tag_ids?: string[]; // Add tag_ids to match backend model
}

export interface FieldMappingSource {
  promptRevId: string;
  promptName: string;
  schemaFieldPath: string;
  schemaFieldName: string;
  schemaFieldType: string;
}

export interface FieldMapping {
  sources: FieldMappingSource[];
  mappingType: 'direct' | 'concatenated' | 'calculated' | 'conditional';
  concatenationSeparator?: string; // For concatenated mappings
}

export interface FormConfig {
  name: string;
  response_format: FormResponseFormat;
  tag_ids?: string[]; // Add tag_ids support
}

export interface CreateFormParams extends FormConfig {
  organizationId: string;
}

export interface ListFormsParams {
  organizationId: string;
  skip?: number;
  limit?: number;
  tag_ids?: string; // Add tag_ids support for filtering
}

export interface ListFormsResponse {
  forms: Form[];
  total_count: number;
  skip: number;
}

export interface GetFormParams {
  organizationId: string;
  formRevId: string; // GET uses form revision ID
}

export interface UpdateFormParams {
  organizationId: string;
  formId: string; // UPDATE uses form ID
  form: FormConfig;
}

export interface DeleteFormParams {
  organizationId: string;
  formId: string; // DELETE uses form ID
}

export interface FormSubmissionData {
  form_revid: string;
  submission_data: Record<string, unknown>;
  submitted_by?: string;
}

export interface FormSubmission extends FormSubmissionData {
  id: string;
  organization_id: string;
  created_at: string;
  updated_at: string;
}

export interface SubmitFormParams {
  organizationId: string;
  documentId: string;
  submission: FormSubmissionData;
}

export interface GetFormSubmissionParams {
  organizationId: string;
  documentId: string;
  formRevId: string;
}

export interface DeleteFormSubmissionParams {
  organizationId: string;
  documentId: string;
  formRevId: string;
}

export interface FormField {
  key: string;
  label: string;
  type: string;
  path: string[];
}

// Add interface for form component structure
export interface FormComponent {
  key?: string;
  type?: string;
  label?: string;
  components?: FormComponent[];
  columns?: FormComponent[];
  tabs?: FormComponent[];
}