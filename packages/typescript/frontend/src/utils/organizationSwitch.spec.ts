import { describe, expect, it } from 'vitest'

import { organizationSwitchNavigation } from './organizationSwitch'

describe('organizationSwitchNavigation', () => {
  it('navigates to the new org dashboard from work pages and settings that are not about one organization', () => {
    expect(organizationSwitchNavigation('/orgs/old/docs', '?tab=upload', 'new')).toEqual({
      type: 'navigate',
      path: '/orgs/new/dashboard',
      replace: true,
    })
    expect(organizationSwitchNavigation('/orgs/old', '', 'new')).toEqual({
      type: 'navigate',
      path: '/orgs/new/dashboard',
      replace: true,
    })
    expect(organizationSwitchNavigation('/settings/user/profile', '?x=1', 'new')).toEqual({
      type: 'navigate',
      path: '/orgs/new/dashboard',
      replace: true,
    })
    expect(organizationSwitchNavigation('/feedback', '', 'new')).toEqual({
      type: 'navigate',
      path: '/orgs/new/dashboard',
      replace: true,
    })
  })

  it('stays on the same organization settings page', () => {
    expect(organizationSwitchNavigation('/settings/organizations/old', '', 'new')).toEqual({
      type: 'navigate',
      path: '/settings/organizations/new',
      replace: true,
    })
    expect(organizationSwitchNavigation('/settings/organizations/old/subscription', '?tab=1', 'new')).toEqual({
      type: 'navigate',
      path: '/settings/organizations/new/subscription?tab=1',
      replace: true,
    })
    expect(organizationSwitchNavigation('/settings/organizations/old/webhooks', '', 'new')).toEqual({
      type: 'navigate',
      path: '/settings/organizations/new/webhooks',
      replace: true,
    })
  })
})
