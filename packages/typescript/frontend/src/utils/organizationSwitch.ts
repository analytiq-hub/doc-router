export const CURRENT_ORGANIZATION_STORAGE_KEY = 'currentOrganizationId'

export function rememberOrganization(organizationId: string): void {
  localStorage.setItem(CURRENT_ORGANIZATION_STORAGE_KEY, organizationId)
}

export type OrganizationSwitchNavigation =
  | { type: 'none' }
  | { type: 'navigate'; path: string; replace?: boolean }

/**
 * After the header org switcher: an organization settings page stays on the same page of the
 * other organization. Every other page lands on the new organization's dashboard.
 */
export function organizationSwitchNavigation(
  pathname: string,
  search: string,
  organizationId: string,
): OrganizationSwitchNavigation {
  const settingsOrg = pathname.match(/^\/settings\/organizations\/[^/]+(\/.*)?$/)
  if (settingsOrg) {
    return {
      type: 'navigate',
      path: `/settings/organizations/${organizationId}${settingsOrg[1] ?? ''}${search}`,
      replace: true,
    }
  }
  return {
    type: 'navigate',
    path: `/orgs/${organizationId}/dashboard`,
    replace: true,
  }
}
