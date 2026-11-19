/** @vitest-environment node */
import { describe, expect, it } from 'vitest'

import { settingsItemActive, settingsNavGroups } from './SettingsNav'

describe('settingsNavGroups', () => {
  it('includes organization General, Users, OCR, and system Queues when an org and sysadmin are present', () => {
    const groups = settingsNavGroups({
      organizationId: 'org-1',
      organizationName: 'Acme',
      isSysadmin: true,
    })
    const org = groups.find((g) => g.key === 'organization')
    const system = groups.find((g) => g.key === 'system')
    expect(org?.items.map((i) => i.to)).toEqual(
      expect.arrayContaining([
        '/settings/organizations/org-1',
        '/settings/organizations/org-1/users',
        '/settings/organizations/org-1/ocr',
        '/settings/organizations/org-1/subscription',
      ]),
    )
    expect(system?.items.map((i) => i.text)).toEqual(
      expect.arrayContaining(['Queues', 'Rate limits', 'Users', 'License']),
    )
  })

  it('shows only Your organizations when no org is selected', () => {
    const groups = settingsNavGroups({
      organizationId: null,
      organizationName: null,
      isSysadmin: false,
    })
    const org = groups.find((g) => g.key === 'organization')
    expect(org?.items).toEqual([
      expect.objectContaining({ text: 'Your organizations', to: '/settings/organizations' }),
    ])
    expect(groups.some((g) => g.key === 'system')).toBe(false)
  })
})

describe('settingsItemActive', () => {
  it('treats legacy worker-settings as Queues', () => {
    const queues = {
      text: 'Queues',
      icon: undefined as never,
      to: '/settings/account/queues',
      also: ['/settings/account/development/worker-settings'],
    }
    expect(settingsItemActive('/settings/account/development/worker-settings', queues)).toBe(true)
    expect(settingsItemActive('/settings/account/queues', queues)).toBe(true)
    expect(settingsItemActive('/settings/account/limits', queues)).toBe(false)
  })

  it('does not match General when a longer organization path is open', () => {
    const general = {
      text: 'General',
      icon: undefined as never,
      to: '/settings/organizations/org-1',
      exact: true,
    }
    expect(settingsItemActive('/settings/organizations/org-1', general)).toBe(true)
    expect(settingsItemActive('/settings/organizations/org-1/users', general)).toBe(false)
    expect(settingsItemActive('/settings/organizations/org-1/ocr', general)).toBe(false)
  })
})