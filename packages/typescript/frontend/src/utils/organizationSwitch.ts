export const CURRENT_ORGANIZATION_STORAGE_KEY = 'currentOrganizationId'

export function rememberOrganization(organizationId: string): void {
  localStorage.setItem(CURRENT_ORGANIZATION_STORAGE_KEY, organizationId)
}

export type OrganizationSwitchNavigation =
  | { type: 'none' }
  | { type: 'navigate'; path: string; replace?: boolean }

/** After the header org switcher: always land on the new org dashboard (drop query params). */
export function organizationSwitchNavigation(
  _pathname: string,
  _search: string,
  organizationId: string,
): OrganizationSwitchNavigation {
  return {
    type: 'navigate',
    path: `/orgs/${organizationId}/dashboard`,
    replace: true,
  }
}
