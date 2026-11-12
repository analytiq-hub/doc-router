export const CURRENT_ORGANIZATION_STORAGE_KEY = 'currentOrganizationId'

export function rememberOrganization(organizationId: string): void {
  localStorage.setItem(CURRENT_ORGANIZATION_STORAGE_KEY, organizationId)
}

export type OrganizationSwitchNavigation =
  | { type: 'none' }
  | { type: 'navigate'; path: string; replace?: boolean }

/**
 * Where to go after picking another org (mirrors doc-orchestrator TeamSwitcher).
 * - On /orgs/:id/... keep the same sub-path under the new org.
 * - On /settings/organizations/:id/... swap the org segment, keep the rest.
 * - On other /settings/... stay on the page; UI reads remembered org from storage/context.
 * - Else only remember; no route change.
 */
export function organizationSwitchNavigation(
  pathname: string,
  search: string,
  organizationId: string,
): OrganizationSwitchNavigation {
  const settingsOrg = pathname.match(/^\/settings\/organizations\/([^/]+)(\/.*)?$/)
  if (settingsOrg) {
    const suffix = settingsOrg[2] ?? ''
    return { type: 'navigate', path: `/settings/organizations/${organizationId}${suffix}${search}` }
  }

  if (pathname.startsWith('/settings/')) {
    return { type: 'navigate', path: `${pathname}${search}`, replace: true }
  }

  const orgsMatch = pathname.match(/^\/orgs\/[^/]+(\/.*)?$/)
  if (orgsMatch) {
    const suffix = orgsMatch[1] ?? '/dashboard'
    return { type: 'navigate', path: `/orgs/${organizationId}${suffix}${search}` }
  }

  return { type: 'none' }
}
