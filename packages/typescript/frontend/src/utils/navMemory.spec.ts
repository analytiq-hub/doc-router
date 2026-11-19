/** @vitest-environment jsdom */
import { beforeEach, describe, expect, it } from 'vitest'

import { forgetNavigation, lastAppPath, lastSettingsPath, rememberPath } from './navMemory'

describe('navMemory', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('remembers the last work page and the last settings page', () => {
    rememberPath('/orgs/org-1/docs', '?tab=1')
    rememberPath('/settings/user/profile', '')
    expect(lastAppPath()).toBe('/orgs/org-1/docs?tab=1')
    expect(lastSettingsPath()).toBe('/settings/user/profile')
  })

  it('does not remember addresses that only forward', () => {
    rememberPath('/settings/organizations/org-1', '')
    rememberPath('/settings/user/developer', '')
    rememberPath('/settings/account/development', '?x=1')
    rememberPath('/settings/account/development/worker-settings', '')
    rememberPath('/settings/organizations/org-1/webhooks', '')
    expect(lastSettingsPath()).toBe('/settings/organizations/org-1')
  })

  it('remembers queues and organization subpages as return targets', () => {
    rememberPath('/settings/account/queues', '')
    expect(lastSettingsPath()).toBe('/settings/account/queues')
    rememberPath('/settings/organizations/org-1/users', '')
    expect(lastSettingsPath()).toBe('/settings/organizations/org-1/users')
    rememberPath('/settings/account/limits', '?x=1')
    expect(lastSettingsPath()).toBe('/settings/account/limits?x=1')
  })

  it('ignores a stored address that is not a settings or work page', () => {
    localStorage.setItem('lastSettingsPath', 'https://example.com')
    localStorage.setItem('lastAppPath', '/settings/user/profile')
    expect(lastSettingsPath()).toBeNull()
    expect(lastAppPath()).toBeNull()
  })

  it('forgets both on sign-out', () => {
    rememberPath('/orgs/org-1/dashboard', '')
    rememberPath('/settings/account/license', '')
    forgetNavigation()
    expect(lastAppPath()).toBeNull()
    expect(lastSettingsPath()).toBeNull()
  })
})
