/** @vitest-environment jsdom */
import { cleanup, fireEvent, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { renderOrgHub } from '@/test/orgHubHarness'
import {
  hubFlowCredential,
  hubFlowCredentialKind,
  hubFlowDetail,
  hubFlowExecution,
  hubFlowNodeTypes,
  hubFlowRevision,
  ORG_HUB_ID,
} from '@/test/fixtures/orgHubRows'

const listFlowCredentialsMock = vi.hoisted(() => vi.fn())
const listFlowCredentialKindsMock = vi.hoisted(() => vi.fn())
const listExecutionsMock = vi.hoisted(() => vi.fn())
const listFlowNodeTypesMock = vi.hoisted(() => vi.fn())
const getFlowMock = vi.hoisted(() => vi.fn())
const getRevisionMock = vi.hoisted(() => vi.fn())

const useOrgCapabilityMock = vi.hoisted(() =>
  vi.fn(() => ({
    hasCapability: true,
    loading: false,
  })),
)

const searchParamsMock = vi.hoisted(() => ({
  params: new URLSearchParams(),
}))

vi.mock('@/hooks/useOrgPermissions', () => ({
  useOrgCapability: (...args: unknown[]) => useOrgCapabilityMock(...args),
  useOrgCapabilityTabGuard: vi.fn(),
  useOrgCapabilityRouteGuard: () => ({ blocked: false, loading: false }),
}))

vi.mock('@/utils/appRouter', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => searchParamsMock.params,
  useParams: () => ({ organizationId: ORG_HUB_ID }),
}))

vi.mock('@/components/flows/FlowEditor', () => ({
  default: () => <div data-testid="flow-editor-stub">Flow editor</div>,
}))

vi.mock('@/components/flows/FlowExecutionsView', () => ({
  default: () => <div data-testid="flow-executions-stub">Executions view</div>,
}))

vi.mock('@/components/flows/FlowLogsPanel', () => ({
  default: () => null,
}))

vi.mock('@/components/flows/FlowEditorChatPanel', () => ({
  default: () => null,
}))

vi.mock('react-resizable-panels', () => ({
  Panel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PanelGroup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PanelResizeHandle: () => null,
}))

vi.mock('@/components/flows/useFlowApi', () => ({
  useFlowApi: () => ({
    listFlowCredentials: listFlowCredentialsMock,
    listFlowCredentialKinds: listFlowCredentialKindsMock,
    listExecutions: listExecutionsMock,
    listFlowNodeTypes: listFlowNodeTypesMock,
    getFlow: getFlowMock,
    getRevision: getRevisionMock,
    getHttpClient: vi.fn(),
    saveRevision: vi.fn(),
    createFlow: vi.fn(),
    activateFlow: vi.fn(),
    deactivateFlow: vi.fn(),
    patchFlow: vi.fn(),
    listExecutionsForFlow: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  }),
}))

vi.mock('@/utils/api', () => ({
  DocRouterOrgApi: class {},
  DocRouterAccountApi: class {},
  getApiErrorMsg: (err: unknown) => (err instanceof Error ? err.message : ''),
}))

import FlowToolbar from '@/components/flows/FlowToolbar'
import FlowNodePalette from '@/components/flows/FlowNodePalette'
import FlowCredentials from '@/components/flows/FlowCredentials'
import FlowExecutionsAll from '@/components/flows/FlowExecutionsAll'
import FlowDetailPageClient from '@/pages/orgs/flow-detail-client'
import { NEW_FLOW_URL_SEGMENT } from '@/components/flows/flowDefaultNames'

function resetFlowMocks() {
  listFlowCredentialsMock.mockReset()
  listFlowCredentialsMock.mockResolvedValue({ items: [hubFlowCredential], total: 1 })
  listFlowCredentialKindsMock.mockReset()
  listFlowCredentialKindsMock.mockResolvedValue([hubFlowCredentialKind])
  listExecutionsMock.mockReset()
  listExecutionsMock.mockResolvedValue({ items: [hubFlowExecution], total: 1 })
  listFlowNodeTypesMock.mockReset()
  listFlowNodeTypesMock.mockResolvedValue({ items: hubFlowNodeTypes })
  getFlowMock.mockReset()
  getFlowMock.mockResolvedValue(hubFlowDetail)
  getRevisionMock.mockReset()
  getRevisionMock.mockResolvedValue(hubFlowRevision)
}

describe('flow screens and workspace components', () => {
  afterEach(() => {
    cleanup()
    searchParamsMock.params = new URLSearchParams()
  })

  beforeEach(() => {
    resetFlowMocks()
    useOrgCapabilityMock.mockImplementation(() => ({
      hasCapability: true,
      loading: false,
    }))
  })

  it('renders flow toolbar actions', () => {
    const { container } = renderOrgHub(
      <FlowToolbar
        name="Inbound OCR"
        onNameChange={vi.fn()}
        active={false}
        isDirty={false}
        isSaving={false}
        onSave={vi.fn()}
        onActivate={vi.fn()}
        onDeactivate={vi.fn()}
        onDownloadFlowJson={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    )
    expect(within(container).getByTitle('Inbound OCR')).toBeInTheDocument()
    expect(within(container).getByRole('button', { name: 'Save' })).toBeDisabled()
    expect(within(container).getByRole('button', { name: 'Activate' })).toBeInTheDocument()
  })

  it('lists palette sections for node types', () => {
    const { container } = renderOrgHub(<FlowNodePalette nodeTypes={hubFlowNodeTypes} />)
    fireEvent.click(within(container).getByRole('button', { name: /Trigger \(\d+\)/i }))
    expect(within(container).getByRole('region', { name: /Trigger nodes/i })).toBeInTheDocument()
    expect(within(container).getByText('Manual Trigger')).toBeInTheDocument()
  })

  it('loads credentials workspace table', async () => {
    const { container } = renderOrgHub(<FlowCredentials organizationId={ORG_HUB_ID} />)
    await waitFor(() => {
      expect(within(container).getByText(hubFlowCredential.name)).toBeInTheDocument()
    })
    expect(within(container).getByText('Kind')).toBeInTheDocument()
    expect(listFlowCredentialsMock).toHaveBeenCalled()
  })

  it('loads org-wide executions table', async () => {
    const { container } = renderOrgHub(<FlowExecutionsAll organizationId={ORG_HUB_ID} />)
    await waitFor(() => {
      expect(within(container).getByText(hubFlowExecution.flow_name!)).toBeInTheDocument()
    })
    expect(within(container).getByText('Succeeded')).toBeInTheDocument()
    expect(listExecutionsMock).toHaveBeenCalled()
  })

  it('loads an existing flow into the editor workspace', async () => {
    const { container } = renderOrgHub(
      <FlowDetailPageClient organizationId={ORG_HUB_ID} flowId="flow-1" />,
    )
    await waitFor(() => {
      expect(within(container).getByTitle(hubFlowDetail.flow.name)).toBeInTheDocument()
    })
    expect(within(container).getByTestId('flow-editor-stub')).toBeInTheDocument()
    expect(within(container).getByRole('tab', { name: 'Editor' })).toBeInTheDocument()
    expect(getFlowMock).toHaveBeenCalledWith('flow-1')
    expect(listFlowNodeTypesMock).toHaveBeenCalled()
    expect(getRevisionMock).toHaveBeenCalled()
  })

  it('loads a draft flow from proposedName', async () => {
    searchParamsMock.params = new URLSearchParams('proposedName=Claims+router')
    const { container } = renderOrgHub(
      <FlowDetailPageClient organizationId={ORG_HUB_ID} flowId={NEW_FLOW_URL_SEGMENT} />,
    )
    await waitFor(() => {
      expect(within(container).getByTitle('Claims router')).toBeInTheDocument()
    })
    expect(within(container).getByTestId('flow-editor-stub')).toBeInTheDocument()
    expect(within(container).getByRole('tab', { name: 'Executions' })).toBeDisabled()
    expect(getFlowMock).not.toHaveBeenCalled()
    expect(listFlowNodeTypesMock).toHaveBeenCalled()
  })

  it('opens executions view when tab query is set', async () => {
    searchParamsMock.params = new URLSearchParams('tab=executions')
    const { container } = renderOrgHub(
      <FlowDetailPageClient organizationId={ORG_HUB_ID} flowId="flow-1" />,
    )
    await waitFor(() => {
      expect(within(container).getByTitle(hubFlowDetail.flow.name)).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(within(container).getByTestId('flow-executions-stub')).toBeInTheDocument()
    })
  })
})