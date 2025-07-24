export interface FormProperty {
  type: 'string' | 'integer' | 'number' | 'boolean' | 'array' | 'object';
  description?: string;
  items?: FormProperty;  // For array types
  properties?: Record<string, FormProperty>;  // For object types
  additionalProperties?: boolean;  // Add this for object types
  required?: string[];  // Add this for object types to specify required properties
}

export interface FormResponseFormat {
  type: 'json_form';
  json_form: {
    name: string;
    form: {
      type: 'object';
      properties: Record<string, FormProperty>;
      required: string[];
      additionalProperties: boolean;
    };
    strict: boolean;
  };
}

export interface Form {
  form_revid: string; // MongoDB's _id
  form_id: string;  // Stable identifier
  name: string;
  response_format: FormResponseFormat;
  form_version: number;
  created_at: string;
  created_by: string;
}

export type FormElementType =
  | 'text'
  | 'number'
  | 'dropdown'
  | 'checkbox'
  | 'textarea'
  | 'table'
  | 'note'; // Add note type

export interface FormNodeData {
  id: string; // unique node id
  type: FormElementType;
  name: string; // label or note title
  key: string; // for data binding (not needed for notes)
  position: { x: number; y: number };
  width?: number;
  height?: number;
  // --- Field-specific properties ---
  placeholder?: string;
  required?: boolean;
  requiredExpression?: string;
  defaultValue?: string | number | boolean;
  helpText?: string;
  options?: { label: string; value: string }[]; // For dropdowns
  columns?: FormNodeData[]; // For table type: columns definition
  noteContent?: string; // For note type
}

export interface FormConfig {
  name: string;
  response_format: FormResponseFormat;
}

export interface CreateFormParams extends FormConfig {
  organizationId: string;
}

export interface ListFormsParams {
  organizationId: string;
  skip?: number;
  limit?: number;
}

export interface ListFormsResponse {
  forms: Form[];
  total_count: number;
  skip: number;
}

export interface GetFormParams {
  organizationId: string;
  formId: string;
}

export interface UpdateFormParams {
  organizationId: string;
  formId: string;
  form: FormConfig;
}

export interface DeleteFormParams {
  organizationId: string;
  formId: string;
}