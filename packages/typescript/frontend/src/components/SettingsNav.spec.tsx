/** @vitest-environment jsdom */
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { SettingsNav, backTarget } from './SettingsNav'
import { TooltipProvider } from '@/components/ui/tooltip'

function renderNav(
  pathname: string,
  over: Partial<{
    open: boolean
    organizationId: string | null
    organizationName: string | null
    isSysadmin: boolean
    lastAppPath: string | null
  }> = {},
) {
  render(
    <TooltipProvider>
      <MemoryRouter initialEntries={[pathname]}>
        <nav aria-label="Main">
          <SettingsNav
            open
            pathname={pathname}
            organizationId="org-1"
            organizationName="Acme"
            isSysadmin
            lastAppPath="/orgs/org-1/docs?tab=1"
            fallbackTo="/dashboard"
            {...over}
          />
        </nav>
      </MemoryRouter>
    </TooltipProvider>,
  )
  return screen.getByRole('navigation', { name: 'Main' })
}

const sections = (nav: HTMLElement) =>
  within(nav)
    .getAllByRole('link')
    .filter((link) => link.hasAttribute('aria-expanded'))
    .map((link) => [link.textContent, link.getAttribute('aria-expanded')])

describe('SettingsNav', () => {
  afterEach(() => {
    cleanup()
  })

  it('replaces the work menu with User, Organization, and System, expanding the open section', () => {
    const nav = renderNav('/settings/organizations/org-1')
    expect(within(nav).getByRole('link', { name: 'Back to Documents' })).toHaveAttribute(
      'href',
      '/orgs/org-1/docs?tab=1',
    )
    expect(sections(nav)).toEqual([
      ['User', 'false'],
      ['OrganizationAcme', 'true'],
      ['System', 'false'],
    ])
    expect(within(nav).getByRole('link', { name: 'General' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).queryByRole('link', { name: 'Profile' })).toBeNull()
    expect(within(nav).queryByRole('link', { name: 'Documents' })).toBeNull()
  })

  it('omits System for someone who is not a sysadmin, and organization pages when none is selected', () => {
    const nav = renderNav('/settings/organizations', {
      organizationId: null,
      organizationName: null,
      isSysadmin: false,
    })
    expect(sections(nav)).toEqual([
      ['User', 'false'],
      ['Organization', 'true'],
    ])
    expect(within(nav).getByRole('link', { name: 'Your organizations' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).queryByRole('link', { name: 'General' })).toBeNull()
    expect(within(nav).queryByRole('link', { name: 'Users' })).toBeNull()
  })

  it('highlights the parent item on a nested settings page', () => {
    const nav = renderNav('/settings/account/development/llm-manager/providers/openai')
    expect(sections(nav)).toEqual([
      ['User', 'false'],
      ['OrganizationAcme', 'false'],
      ['System', 'true'],
    ])
    expect(within(nav).getByRole('link', { name: 'LLM' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('link', { name: 'AWS' })).not.toHaveAttribute('aria-current')
  })

  it('treats AWS credentials as the AWS page', () => {
    const nav = renderNav('/settings/account/development/aws-credentials')
    expect(within(nav).getByRole('link', { name: 'AWS' })).toHaveAttribute('aria-current', 'page')
  })

  it('shows every page icon, without section headings, when the navigation is closed', () => {
    const nav = renderNav('/settings/user/profile', { open: false })
    expect(within(nav).queryAllByRole('link').some((link) => link.hasAttribute('aria-expanded'))).toBe(false)
    expect(within(nav).getByRole('link', { name: 'Profile' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('link', { name: 'Queues' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Rate limits' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Back to Documents' })).toBeInTheDocument()
  })
})

describe('backTarget', () => {
  it('names the work page the user came from', () => {
    expect(backTarget('/orgs/org-1/flows/flow-9', '/dashboard')).toEqual({
      to: '/orgs/org-1/flows/flow-9',
      label: 'Back to Flows',
    })
  })

  it('falls back when the last page is not a work page', () => {
    expect(backTarget(null, '/dashboard')).toEqual({ to: '/dashboard', label: 'Back to the app' })
    expect(backTarget('/settings/user/profile', '/orgs/org-1/dashboard')).toEqual({
      to: '/orgs/org-1/dashboard',
      label: 'Back to the app',
    })
  })
})
