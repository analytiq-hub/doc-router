/** @vitest-environment jsdom */
import { cleanup, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { listQueryResult, ORG_HUB_ID, orgHubQueryData, renderOrgHub } from '@/test/orgHubHarness'
import {
  hubForm,
  hubKnowledgeBase,
  hubKbDocument,
  hubPrompt,
  hubSchema,
  hubTag,
} from '@/test/fixtures/orgHubRows'

const useOrgCapabilityMock = vi.hoisted(() =>
  vi.fn(() => ({
    hasCapability: true,
    loading: false,
  })),
)

const searchParamsMock = vi.hoisted(() => ({
  params: new URLSearchParams(),
}))

const routeParamsMock = vi.hoisted(() => ({
  organizationId: 'org-hub-test',
  tagId: 'tag-1',
  promptRevId: 'prompt-rev-1',
  schemaRevId: 'schema-rev-1',
  formId: 'form-1',
  id: 'doc-1',
}))

vi.mock('@/hooks/useOrgPermissions', () => ({
  useOrgCapability: (...args: unknown[]) => useOrgCapabilityMock(...args),
  useOrgCapabilityTabGuard: vi.fn(),
  useOrgCapabilityRouteGuard: () => ({ blocked: false, loading: false }),
}))

vi.mock('@/utils/appRouter', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => searchParamsMock.params,
  useParams: () => routeParamsMock,
}))

vi.mock('@/components/doc/DocumentViewerPage', () => ({
  default: ({ organizationId, id }: { organizationId: string; id: string }) => (
    <div data-testid="document-viewer-stub">
      {organizationId}:{id}
    </div>
  ),
}))

vi.mock('@/utils/api', () => ({
  DocRouterOrgApi: class {
    getTag = vi.fn().mockResolvedValue(hubTag)
    getSchema = vi.fn().mockResolvedValue(hubSchema)
    getPrompt = vi.fn().mockResolvedValue(hubPrompt)
    getForm = vi.fn().mockResolvedValue({
      form_id: hubForm.form_id,
      form_revid: 'form-1',
      name: hubForm.name,
      form_version: hubForm.form_version,
      tag_ids: hubForm.tag_ids,
      fields: [],
      created_at: hubForm.created_at,
    })
    getKnowledgeBase = vi.fn().mockResolvedValue(hubKnowledgeBase)
    listKbChatThreads = vi.fn().mockResolvedValue([])
    listTags = vi.fn().mockResolvedValue({ tags: [hubTag], total_count: 1 })
    listSchemaVersions = vi.fn().mockResolvedValue({ schemas: [hubSchema] })
    listPromptVersions = vi.fn().mockResolvedValue({ prompts: [hubPrompt] })
    listFormVersions = vi.fn().mockResolvedValue({
      forms: [
        {
          form_id: hubForm.form_id,
          form_revid: 'form-1',
          name: hubForm.name,
          form_version: hubForm.form_version,
          tag_ids: hubForm.tag_ids,
          fields: [],
          created_at: hubForm.created_at,
        },
      ],
    })
    searchKnowledgeBase = vi.fn()
  },
  DocRouterAccountApi: class {
    getUser = vi.fn().mockResolvedValue({ name: 'Test User' })
    listLLMModels = vi.fn().mockResolvedValue({
      chat_models: [{ litellm_model: 'gpt-4.1-mini' }],
      embedding_models: [{ litellm_model: 'text-embedding-3-small' }],
    })
  },
  getApiErrorMsg: () => '',
}))

vi.mock('@/api/orgQueries', () => ({
  useOrgTags: () => listQueryResult(orgHubQueryData.tags),
  useOrgAllTags: () => listQueryResult(orgHubQueryData.allTags),
  useOrgSchemas: () => listQueryResult(orgHubQueryData.schemas),
  useOrgKBDocuments: () =>
    listQueryResult({
      documents: [hubKbDocument],
      total_count: 1,
    }),
  useInvalidateOrgLists: () => ({
    knowledgeBases: vi.fn(),
    tags: vi.fn(),
    schemas: vi.fn(),
    prompts: vi.fn(),
    forms: vi.fn(),
  }),
}))

import KnowledgeBasesPage from '@/pages/orgs/knowledge-bases'
import KnowledgeBaseSearch from '@/components/KnowledgeBaseSearch'
import KnowledgeBaseDocuments from '@/components/KnowledgeBaseDocuments'
import KnowledgeBaseChat from '@/components/KnowledgeBaseChat'
import TagEditPage from '@/pages/orgs/tag-edit'
import SchemaEditPage from '@/pages/orgs/schema-edit'
import PromptEditPage from '@/pages/orgs/prompt-edit'
import FormEditPage from '@/pages/orgs/form-edit'
import OrgDocumentPage from '@/pages/orgs/document-viewer'

describe('org hub detail routes', () => {
  afterEach(() => {
    cleanup()
    searchParamsMock.params = new URLSearchParams()
  })

  beforeEach(() => {
    useOrgCapabilityMock.mockImplementation(() => ({
      hasCapability: true,
      loading: false,
    }))
  })

  describe('Knowledge base workspace', () => {
    it('shows search tab for a selected knowledge base', () => {
      searchParamsMock.params = new URLSearchParams('tab=search&kbId=kb-1')
      const { container } = renderOrgHub(
        <KnowledgeBasesPage params={Promise.resolve({ organizationId: ORG_HUB_ID })} organizationId={ORG_HUB_ID} />,
      )
      expect(within(container).getByRole('button', { name: 'search' })).toBeInTheDocument()
      expect(within(container).getByRole('heading', { name: 'Search Knowledge Base' })).toBeInTheDocument()
    })

    it('shows documents tab table for a selected knowledge base', async () => {
      searchParamsMock.params = new URLSearchParams('tab=documents&kbId=kb-1')
      const { container } = renderOrgHub(
        <KnowledgeBasesPage params={Promise.resolve({ organizationId: ORG_HUB_ID })} organizationId={ORG_HUB_ID} />,
      )
      await waitFor(() => {
        expect(within(container).getByText(hubKbDocument.document_name)).toBeInTheDocument()
      })
      expect(within(container).getByRole('heading', { name: 'Documents in knowledge base' })).toBeInTheDocument()
    })

    it('shows chat tab empty state for a selected knowledge base', async () => {
      searchParamsMock.params = new URLSearchParams('tab=chat&kbId=kb-1')
      const { container } = renderOrgHub(
        <KnowledgeBasesPage params={Promise.resolve({ organizationId: ORG_HUB_ID })} organizationId={ORG_HUB_ID} />,
      )
      await waitFor(() => {
        expect(within(container).getByText('Chat with Knowledge Base')).toBeInTheDocument()
      })
      expect(
        within(container).getByText('Start a conversation with your knowledge base'),
      ).toBeInTheDocument()
    })

    it('shows edit tab when config write is allowed', async () => {
      searchParamsMock.params = new URLSearchParams('tab=edit&kbId=kb-1')
      const { container } = renderOrgHub(
        <KnowledgeBasesPage params={Promise.resolve({ organizationId: ORG_HUB_ID })} organizationId={ORG_HUB_ID} />,
      )
      await waitFor(() => {
        expect(within(container).getByText('Edit Knowledge Base')).toBeInTheDocument()
      })
      expect(within(container).getByRole('button', { name: 'Update Knowledge Base' })).toBeInTheDocument()
    })

    it('mounts KB search component directly', () => {
      const { container } = renderOrgHub(<KnowledgeBaseSearch organizationId={ORG_HUB_ID} kbId="kb-1" />)
      expect(within(container).getByRole('heading', { name: 'Search Knowledge Base' })).toBeInTheDocument()
    })

    it('mounts KB documents component directly', async () => {
      const { container } = renderOrgHub(<KnowledgeBaseDocuments organizationId={ORG_HUB_ID} kbId="kb-1" />)
      await waitFor(() => {
        expect(within(container).getByText(hubKbDocument.document_name)).toBeInTheDocument()
      })
    })

    it('mounts KB chat component directly', async () => {
      const { container } = renderOrgHub(<KnowledgeBaseChat organizationId={ORG_HUB_ID} kbId="kb-1" />)
      await waitFor(() => {
        expect(within(container).getByText('Chat with Knowledge Base')).toBeInTheDocument()
      })
    })
  })

  describe('Config edit routes', () => {
    it('renders tag edit after load', async () => {
      const { container } = renderOrgHub(<TagEditPage />)
      await waitFor(() => {
        expect(within(container).getByText('Edit tag')).toBeInTheDocument()
      })
      expect(within(container).getByRole('button', { name: '← Back to Tags' })).toBeInTheDocument()
    })

    it('renders schema edit after load', async () => {
      const { container } = renderOrgHub(<SchemaEditPage />)
      await waitFor(() => {
        expect(within(container).getByText('Edit Schema')).toBeInTheDocument()
      })
      expect(within(container).getByRole('button', { name: '← Back to Schemas' })).toBeInTheDocument()
    })

    it('renders prompt edit after load', async () => {
      const { container } = renderOrgHub(<PromptEditPage />)
      await waitFor(() => {
        expect(within(container).getByText('Edit Prompt')).toBeInTheDocument()
      })
      expect(within(container).getByRole('button', { name: '← Back to Prompts' })).toBeInTheDocument()
    })

    it('renders form edit after load', async () => {
      const { container } = renderOrgHub(<FormEditPage />)
      await waitFor(() => {
        expect(within(container).getByText('Edit Form')).toBeInTheDocument()
      })
      expect(within(container).getByRole('button', { name: '← Back to Forms' })).toBeInTheDocument()
    })
  })

  describe('Document viewer route', () => {
    it('forwards org and document id to the viewer page', () => {
      const { container } = renderOrgHub(
        <OrgDocumentPage
          params={Promise.resolve({ organizationId: ORG_HUB_ID, id: 'doc-1' })}
          organizationId={ORG_HUB_ID}
          id="doc-1"
        />,
      )
      expect(within(container).getByTestId('document-viewer-stub')).toHaveTextContent(`${ORG_HUB_ID}:doc-1`)
    })
  })
})