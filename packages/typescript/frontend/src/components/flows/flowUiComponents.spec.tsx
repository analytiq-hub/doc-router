/** @vitest-environment jsdom */
import { cleanup, fireEvent, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { renderOrgHub } from '@/test/orgHubHarness'

const routerPushMock = vi.hoisted(() => vi.fn())

vi.mock('@/utils/appRouter', () => ({
  useRouter: () => ({ push: routerPushMock, replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({ organizationId: 'org-hub-test' }),
}))

import FlowStatusBadge from '@/components/flows/FlowStatusBadge'
import FlowCreate from '@/components/flows/FlowCreate'
import { FlowDisclosure } from '@/components/flows/FlowDisclosure'
import FlowCanvasViewTabs from '@/components/flows/FlowCanvasViewTabs'
import { ORG_HUB_ID } from '@/test/fixtures/orgHubRows'
import { NEW_FLOW_URL_SEGMENT } from '@/components/flows/flowDefaultNames'

describe('flow UI primitives', () => {
  afterEach(() => {
    cleanup()
    routerPushMock.mockReset()
  })

  it('renders active and inactive status badges', () => {
    const active = renderOrgHub(<FlowStatusBadge active />)
    const inactive = renderOrgHub(<FlowStatusBadge active={false} />)
    expect(within(active.container).getByText('Active')).toBeInTheDocument()
    expect(within(inactive.container).getByText('Inactive')).toBeInTheDocument()
  })

  it('submits a new flow name to the draft route', () => {
    const { container } = renderOrgHub(<FlowCreate organizationId={ORG_HUB_ID} />)
    const nameInput = within(container).getByLabelText('Flow name')
    fireEvent.change(nameInput, { target: { value: 'Claims OCR' } })
    fireEvent.click(within(container).getByRole('button', { name: 'Create Flow' }))
    expect(routerPushMock).toHaveBeenCalledWith(
      `/orgs/${ORG_HUB_ID}/flows/${NEW_FLOW_URL_SEGMENT}?proposedName=Claims+OCR`,
    )
  })

  it('shows a validation message when flow name is empty', () => {
    const { container } = renderOrgHub(<FlowCreate organizationId={ORG_HUB_ID} />)
    fireEvent.click(within(container).getByRole('button', { name: 'Create Flow' }))
    expect(within(container).getByText('Flow name is required')).toBeInTheDocument()
    expect(routerPushMock).not.toHaveBeenCalled()
  })

  it('toggles flow disclosure content', () => {
    const { container } = renderOrgHub(
      <FlowDisclosure defaultOpen={false}>
        {({ open, toggle }) => (
          <div>
            <button type="button" onClick={toggle}>
              Toggle
            </button>
            {open ? <p>Panel body</p> : null}
          </div>
        )}
      </FlowDisclosure>,
    )
    expect(within(container).queryByText('Panel body')).not.toBeInTheDocument()
    fireEvent.click(within(container).getByRole('button', { name: 'Toggle' }))
    expect(within(container).getByText('Panel body')).toBeInTheDocument()
  })

  it('switches editor and executions tabs', () => {
    const onChange = vi.fn()
    const { container } = renderOrgHub(
      <FlowCanvasViewTabs value="editor" onChange={onChange} disableExecutionsTab={false} />,
    )
    fireEvent.click(within(container).getByRole('tab', { name: 'Executions' }))
    expect(onChange).toHaveBeenCalledWith('executions')
  })

  it('disables executions tab for unsaved flows', () => {
    const { container } = renderOrgHub(
      <FlowCanvasViewTabs value="editor" onChange={vi.fn()} disableExecutionsTab />,
    )
    expect(within(container).getByRole('tab', { name: 'Executions' })).toBeDisabled()
  })
})