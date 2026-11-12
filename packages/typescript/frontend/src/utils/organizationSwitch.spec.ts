import { describe, expect, it } from 'vitest'

import { organizationSwitchNavigation } from './organizationSwitch'

describe('organizationSwitchNavigation', () => {
  it('always navigates to the new org dashboard', () => {
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
    expect(organizationSwitchNavigation('/settings/organizations/old/webhooks', '', 'new')).toEqual({
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
})
