/** @vitest-environment jsdom */
import { cleanup, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { listQueryResult, ORG_HUB_ID, orgHubQueryData, renderOrgHub } from '@/test/orgHubHarness'
import {
  hubCase,
  hubDocument,
  hubFlowCredential,
  hubFlowCredentialKind,
  hubFlowExecution,
  hubFlowListItem,
  hubForm,
  hubKnowledgeBase,
  hubPrompt,
  hubSchema,
  hubTag,
} from '@/test/fixtures/orgHubRows'
import {
  expectHubTable,
  expectRowActionMenu,
  latestOpenMenu,
  openRowActionsMenu,
} from '@/test/orgHubTestUtils'
import { CAP_CONFIG_WRITE, CAP_DOCUMENTS_WRITE } from '@/utils/orgCapabilities'

const listFlowsMock = vi.hoisted(() => vi.fn())
const listFlowCredentialsMock = vi.hoisted(() => vi.fn())
const listFlowCredentialKindsMock = vi.hoisted(() => vi.fn())
const listExecutionsMock = vi.hoisted(() => vi.fn())
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
  caseId: 'case-claim-1',
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

vi.mock('@/utils/api', () => ({
  DocRouterOrgApi: class {
    deleteTag = vi.fn()
    deleteSchema = vi.fn()
    deletePrompt = vi.fn()
    deleteForm = vi.fn()
    uploadDocument = vi.fn()
    getCase = vi.fn().mockResolvedValue({
      case_id: 'case-claim-1',
      name: 'Claim Alpha',
      tag_ids: [],
      metadata: {},
    })
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
  useOrgDocuments: () => listQueryResult(orgHubQueryData.documents),
  useOrgCases: () => listQueryResult(orgHubQueryData.cases),
  useOrgSchemas: () => listQueryResult(orgHubQueryData.schemas),
  useOrgPrompts: () => listQueryResult(orgHubQueryData.prompts),
  useOrgForms: () => listQueryResult(orgHubQueryData.forms),
  useOrgKnowledgeBases: () => listQueryResult(orgHubQueryData.knowledgeBases),
  useInvalidateOrgLists: () => ({
    tags: vi.fn(),
    documents: vi.fn(),
    cases: vi.fn(),
    schemas: vi.fn(),
    prompts: vi.fn(),
    forms: vi.fn(),
    knowledgeBases: vi.fn(),
  }),
}))

vi.mock('@/components/flows/useFlowApi', () => ({
  useFlowApi: () => ({
    listFlows: listFlowsMock,
    listFlowCredentials: listFlowCredentialsMock,
    listFlowCredentialKinds: listFlowCredentialKindsMock,
    listExecutions: listExecutionsMock,
    runFlow: vi.fn(),
    activateFlow: vi.fn(),
    deactivateFlow: vi.fn(),
    deleteFlow: vi.fn(),
    getRevision: vi.fn(),
    createFlow: vi.fn(),
    testFlowCredential: vi.fn(),
    deleteFlowCredential: vi.fn(),
    stopExecution: vi.fn(),
  }),
}))

import TagList from '@/components/TagList'
import TagsPage from '@/pages/orgs/tags'
import SchemaList from '@/components/SchemaList'
import PromptList from '@/components/PromptList'
import FormList from '@/components/FormList'
import CaseList from '@/components/CaseList'
import OrgDocumentList from '@/components/OrgDocumentList'
import KnowledgeBaseList from '@/components/KnowledgeBaseList'
import FlowList from '@/components/flows/FlowList'
import Dashboard from '@/components/Dashboard'
import FlowsPageClient from '@/pages/orgs/flows-client'
import DocumentsPageClient from '@/pages/orgs/documents-client'
import CasesPage from '@/pages/orgs/cases'
import CaseUpdatePage from '@/pages/orgs/case-update'
import SchemasPage from '@/pages/orgs/schemas'
import PromptsPage from '@/pages/orgs/prompts'
import FormsPage from '@/pages/orgs/forms'
import KnowledgeBasesPage from '@/pages/orgs/knowledge-bases'

function resetFlowApiMocks() {
  listFlowsMock.mockReset()
  listFlowsMock.mockResolvedValue({ items: [hubFlowListItem], total: 1 })
  listFlowCredentialsMock.mockReset()
  listFlowCredentialsMock.mockResolvedValue({ items: [hubFlowCredential], total: 1 })
  listFlowCredentialKindsMock.mockReset()
  listFlowCredentialKindsMock.mockResolvedValue([hubFlowCredentialKind])
  listExecutionsMock.mockReset()
  listExecutionsMock.mockResolvedValue({ items: [hubFlowExecution], total: 1 })
}

describe('org hub list pages', () => {
  afterEach(() => {
    cleanup()
    searchParamsMock.params = new URLSearchParams()
  })

  beforeEach(() => {
    useOrgCapabilityMock.mockImplementation(() => ({
      hasCapability: true,
      loading: false,
    }))
    resetFlowApiMocks()
  })

  describe('Tags', () => {
    it('renders the tags grid with fixture data', () => {
      const { container } = renderOrgHub(<TagList organizationId={ORG_HUB_ID} />)
      expectHubTable(container, 'Tags', ['Name', 'Description', 'Created', 'Actions'], hubTag.name)
    })

    it('shows the page header action when config write is allowed', () => {
      const { container } = renderOrgHub(
        <TagsPage params={Promise.resolve({ organizationId: ORG_HUB_ID })} organizationId={ORG_HUB_ID} />,
      )
      expect(within(container).getByRole('heading', { name: 'Tags' })).toBeInTheDocument()
      expect(within(container).getByRole('button', { name: 'New tag' })).toBeInTheDocument()
      expectHubTable(container, 'Tags', ['Name', 'Description', 'Created', 'Actions'], hubTag.name)
    })

    it('exposes expected row actions', async () => {
      const { container } = renderOrgHub(<TagList organizationId={ORG_HUB_ID} />)
      await expectRowActionMenu(container, hubTag.name, ['Properties', 'Edit', 'Delete'])
    })

    it('hides create actions without config write', () => {
      useOrgCapabilityMock.mockImplementation((_org, cap) => ({
        hasCapability: cap !== CAP_CONFIG_WRITE,
        loading: false,
      }))
      const { container } = renderOrgHub(
        <TagsPage params={Promise.resolve({ organizationId: ORG_HUB_ID })} organizationId={ORG_HUB_ID} />,
      )
      expect(within(container).queryByRole('button', { name: 'New tag' })).not.toBeInTheDocument()
    })
  })

  describe('Schemas', () => {
    it('renders the schemas grid', () => {
      const { container } = renderOrgHub(<SchemaList organizationId={ORG_HUB_ID} />)
      expectHubTable(container, 'Schemas', ['Schema', 'Fields', 'Version', 'Created', 'Actions'], hubSchema.name)
    })
  })

  describe('Prompts', () => {
    it('renders the prompts grid', () => {
      const { container } = renderOrgHub(<PromptList organizationId={ORG_HUB_ID} />)
      expectHubTable(
        container,
        'Prompts',
        ['Prompt', 'Tags', 'Schema', 'Model', 'Version', 'Saved', 'Actions'],
        hubPrompt.name,
      )
    })

    it('exposes expected row actions', async () => {
      const { container } = renderOrgHub(<PromptList organizationId={ORG_HUB_ID} />)
      await expectRowActionMenu(container, hubPrompt.name, [
        'Properties',
        'Edit',
        'Rename',
        'Clone',
        'Download',
        'Delete',
      ])
    })
  })

  describe('Forms', () => {
    it('renders the forms grid', () => {
      const { container } = renderOrgHub(<FormList organizationId={ORG_HUB_ID} />)
      expectHubTable(container, 'Forms', ['Form', 'Version', 'Tags', 'Created', 'Actions'], hubForm.name)
    })
  })

  describe('Documents', () => {
    it('renders the documents grid', () => {
      const { container } = renderOrgHub(<OrgDocumentList organizationId={ORG_HUB_ID} />)
      expectHubTable(
        container,
        'Documents',
        ['Document name', 'Upload date', 'Uploaded by', 'Case', 'State', 'Tags', 'Actions'],
        hubDocument.document_name,
      )
    })

    it('exposes Update in the row menu', async () => {
      const { container } = renderOrgHub(<OrgDocumentList organizationId={ORG_HUB_ID} />)
      await expectRowActionMenu(container, hubDocument.document_name, ['Update'])
    })
  })

  describe('Cases', () => {
    it('renders the cases grid', () => {
      const { container } = renderOrgHub(<CaseList organizationId={ORG_HUB_ID} />)
      expectHubTable(
        container,
        'Cases',
        ['Case name', 'Case ID', 'Tags', 'Documents', 'Created', 'Updated', 'Actions'],
        hubCase.name,
      )
    })

    it('exposes Update in the row menu', async () => {
      const { container } = renderOrgHub(<CaseList organizationId={ORG_HUB_ID} />)
      await expectRowActionMenu(container, hubCase.name, ['Update'])
    })
  })

  describe('Knowledge bases', () => {
    it('renders the knowledge bases grid', () => {
      const { container } = renderOrgHub(<KnowledgeBaseList organizationId={ORG_HUB_ID} />)
      expectHubTable(
        container,
        'Knowledge bases',
        ['Name', 'Description', 'Status', 'Documents', 'Chunks', 'Model', 'Tags', 'Created', 'Actions'],
        hubKnowledgeBase.name,
      )
    })
  })

  describe('Flows', () => {
    it('renders the flows table after load', async () => {
      const { container } = renderOrgHub(<FlowList organizationId={ORG_HUB_ID} />)
      await waitFor(() => {
        expect(within(container).getByText(hubFlowListItem.flow.name)).toBeInTheDocument()
      })
      const scope = within(container)
      expect(scope.getByText('Name')).toBeInTheDocument()
      expect(scope.getByText('Actions')).toBeInTheDocument()
      expect(listFlowsMock).toHaveBeenCalled()
    })
  })

  describe('Dashboard', () => {
    it('renders dashboard shell and recent document', async () => {
      const { container } = renderOrgHub(<Dashboard organizationId={ORG_HUB_ID} />)
      expect(within(container).getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
      expect(within(container).getByText('Quick actions')).toBeInTheDocument()
      await waitFor(() => {
        expect(within(container).getByText(hubDocument.document_name)).toBeInTheDocument()
      })
    })
  })

  describe('read-only documents list', () => {
    it('omits Update when documents write is denied', async () => {
      useOrgCapabilityMock.mockImplementation((_org, cap) => ({
        hasCapability: cap !== CAP_DOCUMENTS_WRITE,
        loading: false,
      }))
      const { container } = renderOrgHub(<OrgDocumentList organizationId={ORG_HUB_ID} />)
      expect(within(container).getByText(hubDocument.document_name)).toBeInTheDocument()
      openRowActionsMenu(container, hubDocument.document_name)
      await waitFor(() => {
        expect(latestOpenMenu()).toBeVisible()
      })
      const menu = latestOpenMenu()
      expect(within(menu).getByRole('menuitem', { name: 'Properties' })).toBeInTheDocument()
      expect(within(menu).queryByRole('menuitem', { name: 'Update' })).not.toBeInTheDocument()
    })
  })
})

describe('org hub tab pages', () => {
  afterEach(() => {
    cleanup()
    searchParamsMock.params = new URLSearchParams()
  })

  beforeEach(() => {
    useOrgCapabilityMock.mockImplementation(() => ({
      hasCapability: true,
      loading: false,
    }))
    resetFlowApiMocks()
  })

  describe('Flows workspace', () => {
    it('shows credentials tab table and create action', async () => {
      const { container } = renderOrgHub(
        <FlowsPageClient organizationId={ORG_HUB_ID} tab="credentials" newFlow={false} autoCreateCredential={false} />,
      )
      expect(within(container).getByRole('button', { name: 'Create credential' })).toBeInTheDocument()
      await waitFor(() => {
        expect(within(container).getByText(hubFlowCredential.name)).toBeInTheDocument()
      })
      expect(within(container).getByText('Name')).toBeInTheDocument()
      expect(within(container).getByText('Kind')).toBeInTheDocument()
      expect(listFlowCredentialsMock).toHaveBeenCalled()
    })

    it('shows executions tab table after load', async () => {
      const { container } = renderOrgHub(
        <FlowsPageClient organizationId={ORG_HUB_ID} tab="executions" newFlow={false} autoCreateCredential={false} />,
      )
      await waitFor(() => {
        expect(within(container).getByText(hubFlowExecution.flow_name!)).toBeInTheDocument()
      })
      expect(within(container).getByText('Flow')).toBeInTheDocument()
      expect(within(container).getByText('Status')).toBeInTheDocument()
      expect(listExecutionsMock).toHaveBeenCalled()
    })
  })

  describe('Documents upload tab', () => {
    it('renders upload UI when tab=upload', () => {
      searchParamsMock.params = new URLSearchParams('tab=upload')
      const { container } = renderOrgHub(<DocumentsPageClient organizationId={ORG_HUB_ID} />)
      expect(within(container).getByRole('heading', { name: 'Upload documents' })).toBeInTheDocument()
      expect(within(container).getByRole('button', { name: /Back to documents/i })).toBeInTheDocument()
    })
  })

  describe('Cases create tab', () => {
    it('renders create case form when tab=case-create', () => {
      searchParamsMock.params = new URLSearchParams('tab=case-create')
      const { container } = renderOrgHub(
        <CasesPage params={Promise.resolve({ organizationId: ORG_HUB_ID })} organizationId={ORG_HUB_ID} />,
      )
      expect(within(container).getByRole('heading', { name: 'Create case' })).toBeInTheDocument()
      expect(within(container).getByRole('button', { name: 'Create case' })).toBeInTheDocument()
    })
  })

  describe('Config create tabs', () => {
    it('renders create schema when tab=schema-create', () => {
      searchParamsMock.params = new URLSearchParams('tab=schema-create')
      const { container } = renderOrgHub(
        <SchemasPage params={Promise.resolve({ organizationId: ORG_HUB_ID })} organizationId={ORG_HUB_ID} />,
      )
      expect(within(container).getByRole('heading', { name: 'Create schema' })).toBeInTheDocument()
      expect(within(container).getByRole('button', { name: /Back to schemas/i })).toBeInTheDocument()
    })

    it('renders create prompt when tab=prompt-create', () => {
      searchParamsMock.params = new URLSearchParams('tab=prompt-create')
      const { container } = renderOrgHub(
        <PromptsPage params={Promise.resolve({ organizationId: ORG_HUB_ID })} organizationId={ORG_HUB_ID} />,
      )
      expect(within(container).getByRole('heading', { name: 'Create prompt' })).toBeInTheDocument()
      expect(within(container).getByRole('button', { name: /Back to prompts/i })).toBeInTheDocument()
    })

    it('renders create form when tab=form-create', () => {
      searchParamsMock.params = new URLSearchParams('tab=form-create')
      const { container } = renderOrgHub(
        <FormsPage params={Promise.resolve({ organizationId: ORG_HUB_ID })} organizationId={ORG_HUB_ID} />,
      )
      expect(within(container).getByRole('heading', { name: 'Create form' })).toBeInTheDocument()
      expect(within(container).getByRole('button', { name: /Back to forms/i })).toBeInTheDocument()
    })

    it('renders create knowledge base when tab=kb-create', () => {
      searchParamsMock.params = new URLSearchParams('tab=kb-create')
      const { container } = renderOrgHub(
        <KnowledgeBasesPage
          params={Promise.resolve({ organizationId: ORG_HUB_ID })}
          organizationId={ORG_HUB_ID}
        />,
      )
      expect(within(container).getByRole('heading', { name: 'Create knowledge base' })).toBeInTheDocument()
      expect(within(container).getByRole('button', { name: /Back to knowledge bases/i })).toBeInTheDocument()
    })
  })

  describe('Case update route', () => {
    it('renders update case form for an existing case', async () => {
      const { container } = renderOrgHub(<CaseUpdatePage />)
      await waitFor(() => {
        expect(within(container).getByText('Update case')).toBeInTheDocument()
      })
      expect(within(container).getByRole('button', { name: '← Back to case' })).toBeInTheDocument()
      expect(within(container).getByRole('button', { name: 'Save changes' })).toBeInTheDocument()
    })
  })
})