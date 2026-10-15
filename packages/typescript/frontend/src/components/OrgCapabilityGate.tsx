'use client';

import { ReactNode } from 'react';
import { useOrgCapability } from '@/hooks/useOrgPermissions';
import { OrgCapability } from '@/utils/orgCapabilities';
import { useAppSession } from '@/contexts/AppSessionContext';
import { isSysAdmin } from '@/utils/roles';

type OrgCapabilityGateProps = {
  organizationId: string;
  capability: OrgCapability;
  children: ReactNode;
  /** When true, platform sysadmins see content without the capability (settings/support only). */
  allowSysadmin?: boolean;
  fallback?: ReactNode;
};

export function OrgCapabilityGate({
  organizationId,
  capability,
  children,
  allowSysadmin = false,
  fallback = null,
}: OrgCapabilityGateProps) {
  const { session } = useAppSession();
  const { hasCapability, loading } = useOrgCapability(organizationId, capability);

  if (loading) {
    return null;
  }
  if (allowSysadmin && isSysAdmin(session)) {
    return <>{children}</>;
  }
  if (hasCapability) {
    return <>{children}</>;
  }
  return <>{fallback}</>;
}
