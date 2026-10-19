import { useAppSession } from '@/contexts/AppSessionContext';
import { Organization } from '@/types/organizations';
import { AppSession } from '@/types/AppSession';
import { userHasOrgAdminGroup } from '@/utils/orgPermissionGroups';
import { CAP_ORG_ADMIN, hasOrgCapability } from '@/utils/orgCapabilities';

/** Platform sysadmin (not org Admin permission group). */
export function isSysAdmin(session: AppSession | null): boolean {
  return session?.user?.isSysadmin === true;
}

/** @deprecated Use isSysAdmin; allowedRoles `admin` means platform sysadmin. */
export function useRole() {
  const { session } = useAppSession();
  return { isSysadmin: isSysAdmin(session) };
}

/** Org Admin built-in permission group for the current user. */
export function isOrgAdmin(organization: Organization, session: AppSession | null): boolean {
  if (!session?.user?.id) return false;
  return userHasOrgAdminGroup(organization, session.user.id);
}

/** Prefer effective capabilities from `permissions/me` when available. */
export function hasOrgAdminCapability(capabilities: readonly string[] | null | undefined): boolean {
  return hasOrgCapability(capabilities, CAP_ORG_ADMIN);
}
