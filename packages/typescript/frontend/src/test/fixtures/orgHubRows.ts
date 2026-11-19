export const ORG_HUB_ID = 'org-hub-test'

export const hubTag = {
  id: 'tag-1',
  name: 'auto',
  color: '#0078D4',
  description: 'Automated processing',
  created_at: '2026-01-15T12:00:00.000Z',
}

export const hubDocument = {
  id: 'doc-1',
  document_name: 'sample-policy.pdf',
  upload_date: '2026-01-10T12:00:00.000Z',
  uploaded_by: 'user@test',
  state: 'ready',
  tag_ids: ['tag-1'],
  case_id: undefined as string | undefined,
  metadata: {} as Record<string, string>,
}

export const hubCase = {
  case_id: 'case-claim-1',
  name: 'Claim Alpha',
  tag_ids: [] as string[],
  metadata: {} as Record<string, string>,
  document_count: 2,
  created_at: '2026-01-01T00:00:00.000Z',
  updated_at: '2026-01-02T00:00:00.000Z',
}

export const hubSchema = {
  schema_id: 'schema-1',
  schema_revid: 'schema-rev-1',
  name: 'Invoice schema',
  schema_version: 1,
  created_at: '2026-01-05T00:00:00.000Z',
  response_format: {
    json_schema: {
      schema: {
        type: 'object',
        properties: {
          total: { type: 'number' },
        },
      },
    },
  },
}

export const hubPrompt = {
  prompt_id: 'prompt-1',
  prompt_revid: 'prompt-rev-1',
  name: 'Extract totals',
  prompt_version: 1,
  model: 'gpt-4.1-mini',
  tag_ids: ['tag-1'],
  schema_id: 'schema-1',
  created_at: '2026-01-06T00:00:00.000Z',
  content: 'Extract fields',
}

export const hubForm = {
  form_id: 'form-1',
  name: 'Intake form',
  form_version: 1,
  tag_ids: [] as string[],
  created_at: '2026-01-07T00:00:00.000Z',
}

export const hubKnowledgeBase = {
  kb_id: 'kb-1',
  name: 'FNOL library',
  description: 'First notice of loss documents',
  status: 'ready' as const,
  document_count: 3,
  chunk_count: 12,
  embedding_model: 'text-embedding-3-small',
  tag_ids: [] as string[],
  created_at: '2026-01-08T00:00:00.000Z',
}

export const hubFlowListItem = {
  flow: {
    flow_id: 'flow-1',
    name: 'Inbound OCR',
    active: true,
    flow_version: 1,
    updated_at: '2026-01-09T00:00:00.000Z',
  },
  latest_revision: null,
}

export const hubFlowCredential = {
  credential_id: 'cred-1',
  name: 'Slack workspace',
  kind_key: 'slackOAuth2',
  created_at: '2026-01-09T12:00:00.000Z',
}

export const hubFlowCredentialKind = {
  key: 'slackOAuth2',
  display_name: 'Slack OAuth2',
}

export const hubFlowExecution = {
  execution_id: 'exec-1',
  flow_id: 'flow-1',
  flow_name: 'Inbound OCR',
  status: 'success',
  started_at: '2026-01-10T08:00:00.000Z',
  stopped_at: '2026-01-10T08:00:10.000Z',
}