import { describe, expect, it } from 'vitest'

import { organizationSwitchNavigation } from './organizationSwitch'

describe('organizationSwitchNavigation', () => {
  it('keeps org hub sub-path', () => {
    expect(
      organizationSwitchNavigation('/orgs/old/docs', '?tab=upload', 'new'),
    ).toEqual({ type: 'navigate', path: '/orgs/new/docs?tab=upload' })
  })

  it('defaults org hub to dashboard', () => {
    expect(organizationSwitchNavigation('/orgs/old', '', 'new')).toEqual({
      type: 'navigate',
      path: '/orgs/new/dashboard',
    })
  })

  it('swaps settings org id and keeps suffix', () => {
    expect(organizationSwitchNavigation('/settings/organizations/old/webhooks', '', 'new')).toEqual({
      type: 'navigate',
      path: '/settings/organizations/new/webhooks',
    })
    expect(organizationSwitchNavigation('/settings/organizations/old', '?tab=billing', 'new')).toEqual({
      type: 'navigate',
      path: '/settings/organizations/new?tab=billing',
    })
  })

  it('stays on non-org settings with replace', () => {
    expect(
      organizationSwitchNavigation('/settings/user/profile', '?x=1', 'new'),
    ).toEqual({ type: 'navigate', path: '/settings/user/profile?x=1', replace: true })
  })

  it('does not navigate off global pages', () => {
    expect(organizationSwitchNavigation('/feedback', '', 'new')).toEqual({ type: 'none' })
  })
})
