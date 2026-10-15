import { useAppSession } from '@/contexts/AppSessionContext';
import { Organization } from '@/types/organizations';
import { Session } from 'next-auth';
import { userHasOrgAdminGroup } from '@/utils/orgPermissionGroups';
import { CAP_ORG_ADMIN, hasOrgCapability } from '@/utils/orgCapabilities';

/** Platform sysadmin (not org Admin permission group). */
export function isSysAdmin(session: Session | null): boolean {
  const appUser = session?.user as { isSysadmin?: boolean } | undefined;
  return appUser?.isSysadmin === true;
}

/** @deprecated Use isSysAdmin; allowedRoles `admin` means platform sysadmin. */
export function useRole() {
  const { session } = useAppSession();
  return { isSysadmin: isSysAdmin(session) };
}

/** Org Admin built-in permission group for the current user. */
export function isOrgAdmin(organization: Organization, session: Session | null): boolean {
  if (!session?.user?.id) return false;
  return userHasOrgAdminGroup(organization, session.user.id);
}

/** Prefer effective capabilities from `permissions/me` when available. */
export function hasOrgAdminCapability(capabilities: readonly string[] | null | undefined): boolean {
  return hasOrgCapability(capabilities, CAP_ORG_ADMIN);
}
