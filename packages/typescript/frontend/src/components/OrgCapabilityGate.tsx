'use client';

import { ReactNode } from 'react';
import { useOrganizationCapabilities } from '@/contexts/OrganizationContext';
import { hasOrgCapability, OrgCapability } from '@/utils/orgCapabilities';
import { useAppSession } from '@/contexts/AppSessionContext';
import { isSysAdmin } from '@/utils/roles';

type OrgCapabilityGateProps = {
  capability: OrgCapability;
  children: ReactNode;
  /** When true, platform sysadmins see content without the capability (settings/support only). */
  allowSysadmin?: boolean;
  fallback?: ReactNode;
};

export function OrgCapabilityGate({
  capability,
  children,
  allowSysadmin = false,
  fallback = null,
}: OrgCapabilityGateProps) {
  const { session } = useAppSession();
  const { capabilities, loading } = useOrganizationCapabilities();

  if (loading) {
    return null;
  }
  if (allowSysadmin && isSysAdmin(session)) {
    return <>{children}</>;
  }
  if (hasOrgCapability(capabilities, capability)) {
    return <>{children}</>;
  }
  return <>{fallback}</>;
}
