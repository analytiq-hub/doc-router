import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAppSession } from '@/contexts/AppSessionContext';
import { AppSession } from '@/types/AppSession';
import { fetchOrgPermissionsMe } from '@/utils/orgPermissionsMe';
import { hasOrgCapability, OrgCapability } from '@/utils/orgCapabilities';

export type OrgPermissionsState = {
  capabilities: string[];
  permissionGroupIds: string[];
  persona: string | null;
  /** True while waiting for session token or permissions/me for this org. */
  loading: boolean;
  /** True when capabilities reflect the current organizationId (safe to gate UI). */
  ready: boolean;
  hasCapability: (capability: OrgCapability) => boolean;
};

const emptyPermissions = (): Omit<OrgPermissionsState, 'hasCapability'> => ({
  capabilities: [],
  permissionGroupIds: [],
  persona: null,
  loading: true,
  ready: false,
});

/**
 * Effective org capabilities for the current user (GET .../permissions/me), scoped to organizationId.
 */
export function useOrgPermissions(organizationId: string | undefined): OrgPermissionsState {
  const { session, status, apiAccessToken } = useAppSession();
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [permissionGroupIds, setPermissionGroupIds] = useState<string[]>([]);
  const [persona, setPersona] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [resolvedOrgId, setResolvedOrgId] = useState<string | null>(null);

  useEffect(() => {
    if (!organizationId) {
      setCapabilities([]);
      setPermissionGroupIds([]);
      setPersona(null);
      setResolvedOrgId(null);
      setLoading(false);
      return;
    }
    if (status === 'loading') {
      return;
    }

    const appSession = session as AppSession | null;
    if (!appSession?.user?.id || !apiAccessToken) {
      setCapabilities([]);
      setPermissionGroupIds([]);
      setPersona(null);
      setResolvedOrgId(null);
      setLoading(true);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setCapabilities([]);
    setPermissionGroupIds([]);
    setPersona(null);
    setResolvedOrgId(null);

    void (async () => {
      try {
        const data = await fetchOrgPermissionsMe(organizationId, apiAccessToken);
        if (cancelled) return;
        setCapabilities(data.capabilities ?? []);
        setPermissionGroupIds(data.permission_group_ids ?? []);
        setPersona(data.persona ?? null);
        setResolvedOrgId(organizationId);
      } catch (error) {
        console.error('Failed to load org permissions:', error);
        if (cancelled) return;
        setCapabilities([]);
        setPermissionGroupIds([]);
        setPersona(null);
        setResolvedOrgId(organizationId);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [organizationId, session, status, apiAccessToken]);

  const ready = Boolean(organizationId) && resolvedOrgId === organizationId && !loading;

  const hasCapability = useCallback(
    (capability: OrgCapability) => ready && hasOrgCapability(capabilities, capability),
    [ready, capabilities],
  );

  return {
    capabilities,
    permissionGroupIds,
    persona,
    loading: Boolean(organizationId) && !ready,
    ready,
    hasCapability,
  };
}

export type OrgCapabilityCheck = Omit<OrgPermissionsState, 'hasCapability'> & {
  /** Whether the user has this capability for the org (false while loading). */
  hasCapability: boolean;
};

/** Single capability check; prefer useOrgPermissions when checking multiple caps on one screen. */
export function useOrgCapability(
  organizationId: string | undefined,
  capability: OrgCapability,
): OrgCapabilityCheck {
  const permissions = useOrgPermissions(organizationId);
  return {
    capabilities: permissions.capabilities,
    permissionGroupIds: permissions.permissionGroupIds,
    persona: permissions.persona,
    loading: permissions.loading,
    ready: permissions.ready,
    hasCapability: permissions.hasCapability(capability),
  };
}

/** Redirect away from a route when the user lacks the given capability. */
export function useOrgCapabilityRouteGuard(
  redirectPath: string,
  organizationId: string | undefined,
  capability: OrgCapability,
  enabled = true,
) {
  const router = useRouter();
  const { hasCapability, loading } = useOrgCapability(organizationId, capability);

  useEffect(() => {
    if (!enabled) return;
    if (!loading && !hasCapability) {
      router.replace(redirectPath);
    }
  }, [enabled, loading, hasCapability, redirectPath, router]);

  return { hasCapability, loading, blocked: !loading && !hasCapability };
}

/** Redirect off a guarded tab query value when the user lacks the given capability. */
export function useOrgCapabilityTabGuard(
  organizationId: string,
  tab: string,
  guardedTab: string,
  redirectPath: string,
  capability: OrgCapability,
) {
  const router = useRouter();
  const { hasCapability, loading } = useOrgCapability(organizationId, capability);

  useEffect(() => {
    if (!loading && tab === guardedTab && !hasCapability) {
      router.replace(redirectPath);
    }
  }, [loading, tab, guardedTab, hasCapability, redirectPath, router]);

  return { hasCapability, loading };
}
