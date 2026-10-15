'use client'

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { DocRouterAccountApi, apiClient } from '@/utils/api';
import { Organization } from '@docrouter/sdk'
import { useAppSession } from '@/contexts/AppSessionContext'
import { AppSession } from '@/types/AppSession'
import { usePathname } from 'next/navigation'

interface OrganizationContextType {
  organizations: Organization[]
  currentOrganization: Organization | null
  setCurrentOrganization: (organization: Organization) => void
  switchOrganization: (organizationId: string) => void
  refreshOrganizations: () => Promise<void>
  isLoading: boolean
  /** Effective org capabilities for the current user (from GET .../permissions/me). */
  capabilities: string[]
  permissionGroupIds: string[]
  persona: string | null
  capabilitiesLoading: boolean
  refreshCapabilities: () => Promise<void>
}

export const OrganizationContext = createContext<OrganizationContextType>({
  organizations: [],
  currentOrganization: null,
  setCurrentOrganization: () => {},
  switchOrganization: () => {},
  refreshOrganizations: async () => {},
  isLoading: true,
  capabilities: [],
  permissionGroupIds: [],
  persona: null,
  capabilitiesLoading: false,
  refreshCapabilities: async () => {},
})

export const useOrganization = () => useContext(OrganizationContext)

export const useOrganizationCapabilities = () => {
  const ctx = useContext(OrganizationContext)
  return {
    capabilities: ctx.capabilities,
    permissionGroupIds: ctx.permissionGroupIds,
    persona: ctx.persona,
    loading: ctx.capabilitiesLoading,
    refreshCapabilities: ctx.refreshCapabilities,
  }
}

export const OrganizationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [currentOrganization, setCurrentOrganization] = useState<Organization | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [capabilities, setCapabilities] = useState<string[]>([])
  const [permissionGroupIds, setPermissionGroupIds] = useState<string[]>([])
  const [persona, setPersona] = useState<string | null>(null)
  const [capabilitiesLoading, setCapabilitiesLoading] = useState(false)
  const pathname = usePathname()
  const { session, status } = useAppSession()
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])
  const fetchInFlightRef = useRef(false)

  // Extract organization ID from pathname if we're on an organization-specific page
  const getOrganizationIdFromPath = useCallback(() => {
    // Check for /orgs/[organizationId] paths (telemetry, analytics, etc.)
    const orgsMatch = pathname.match(/^\/orgs\/([^\/]+)/)
    if (orgsMatch) {
      return orgsMatch[1]
    }
    
    // Check for /settings/organizations/[organizationId] paths
    const settingsMatch = pathname.match(/^\/settings\/organizations\/([^\/]+)/)
    return settingsMatch ? settingsMatch[1] : null
  }, [pathname])

  useEffect(() => {
    if (status === 'loading') return;

    const appSession = session as AppSession | null;
    if (!appSession?.user?.id) {
      console.warn('No user ID found in session');
      setIsLoading(false);
      return;
    }

    // Set synchronously before any await so React 18 Strict Mode double-invocation doesn't trigger duplicate fetches
    if (fetchInFlightRef.current) return;
    fetchInFlightRef.current = true;

    const fetchOrganizations = async () => {
      try {
        // Workspace org list (header switcher): memberships only, including for sysadmins.
        // Sysadmins manage other orgs via Settings → Organizations, not the switcher.
        const response = await docRouterAccountApi.listOrganizations({ userId: appSession.user.id, limit: 50 });
        setOrganizations(response.organizations);
      } catch (error) {
        console.error('Failed to fetch organizations:', error);
      } finally {
        setIsLoading(false);
        fetchInFlightRef.current = false;
      }
    };

    fetchOrganizations();
  }, [session, status, docRouterAccountApi]);

  // Sync currentOrganization with URL path - this is the source of truth when on org pages
  useEffect(() => {
    if (organizations.length === 0) return

    // Extract org ID directly from pathname (not via callback to avoid stale closure)
    let orgIdFromPath: string | null = null
    const orgsMatch = pathname.match(/^\/orgs\/([^\/]+)/)
    if (orgsMatch) {
      orgIdFromPath = orgsMatch[1]
    } else {
      const settingsMatch = pathname.match(/^\/settings\/organizations\/([^\/]+)/)
      if (settingsMatch) {
        orgIdFromPath = settingsMatch[1]
      }
    }

    if (orgIdFromPath) {
      // Sync switcher to URL only for orgs the user belongs to (/orgs/... or member settings edit).
      const orgFromPath = organizations.find(org => org.id === orgIdFromPath)
      if (orgFromPath) {
        setCurrentOrganization(prev => {
          if (prev?.id === orgFromPath.id) return prev
          localStorage.setItem('currentOrganizationId', orgFromPath.id)
          return orgFromPath
        })
        return
      }
    }

    // Not on an org-specific page - preserve current selection if valid
    setCurrentOrganization(prev => {
      if (prev && organizations.some(org => org.id === prev.id)) {
        return prev
      }

      // Fallback to stored organization
      const storedOrganizationId = localStorage.getItem('currentOrganizationId')
      if (storedOrganizationId) {
        const storedOrganization = organizations.find(w => w.id === storedOrganizationId)
        if (storedOrganization) {
          return storedOrganization
        }
      }

      // Last resort: use first organization
      localStorage.setItem('currentOrganizationId', organizations[0].id)
      return organizations[0]
    })
  }, [organizations, pathname])

  const switchOrganization = useCallback((organizationId: string) => {
    const organization = organizations.find(w => w.id === organizationId)
    if (organization) {
      setCurrentOrganization(organization)
      localStorage.setItem('currentOrganizationId', organizationId)
      
      // If we're on an organization-specific page, go to the new org's dashboard
      const orgIdFromPath = getOrganizationIdFromPath()
      if (orgIdFromPath && orgIdFromPath !== organizationId) {
        if (pathname.startsWith('/orgs/') || pathname.startsWith('/settings/organizations/')) {
          window.location.href = `/orgs/${organizationId}/dashboard`
        }
      }
    }
  }, [organizations, getOrganizationIdFromPath, pathname])

  const refreshOrganizations = useCallback(async () => {
    try {
      const appSession = session as AppSession | null;
      if (!appSession?.user?.id) {
        console.warn('No user ID found in session');
        return;
      }

      const response = await docRouterAccountApi.listOrganizations({ userId: appSession.user.id, limit: 50 });
      setOrganizations(response.organizations);
    } catch (error) {
      console.error('Failed to refresh organizations:', error);
    }
  }, [session, docRouterAccountApi])

  const refreshCapabilities = useCallback(async () => {
    const appSession = session as AppSession | null
    let orgId = currentOrganization?.id
    const orgsMatch = pathname.match(/^\/orgs\/([^/]+)/)
    if (orgsMatch) {
      orgId = orgsMatch[1]
    } else {
      const settingsMatch = pathname.match(/^\/settings\/organizations\/([^/]+)/)
      if (settingsMatch) {
        orgId = settingsMatch[1]
      }
    }
    if (!appSession?.user?.id || !orgId) {
      setCapabilities([])
      setPermissionGroupIds([])
      setPersona(null)
      return
    }
    setCapabilitiesLoading(true)
    try {
      const { data } = await apiClient.get<{
        capabilities: string[]
        permission_group_ids: string[]
        persona: string | null
      }>(`/v0/orgs/${orgId}/permissions/me`)
      setCapabilities(data.capabilities ?? [])
      setPermissionGroupIds(data.permission_group_ids ?? [])
      setPersona(data.persona ?? null)
    } catch (error) {
      console.error('Failed to load org capabilities:', error)
      setCapabilities([])
      setPermissionGroupIds([])
      setPersona(null)
    } finally {
      setCapabilitiesLoading(false)
    }
  }, [currentOrganization?.id, session, pathname])

  useEffect(() => {
    void refreshCapabilities()
  }, [refreshCapabilities])

  return (
    <OrganizationContext.Provider value={{
      organizations,
      currentOrganization,
      setCurrentOrganization,
      switchOrganization,
      refreshOrganizations,
      isLoading,
      capabilities,
      permissionGroupIds,
      persona,
      capabilitiesLoading,
      refreshCapabilities,
    }}>
      {children}
    </OrganizationContext.Provider>
  )
} 