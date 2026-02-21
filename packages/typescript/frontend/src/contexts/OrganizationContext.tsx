'use client'

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { DocRouterAccountApi } from '@/utils/api'
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
}

export const OrganizationContext = createContext<OrganizationContextType>({
  organizations: [],
  currentOrganization: null,
  setCurrentOrganization: () => {},
  switchOrganization: () => {},
  refreshOrganizations: async () => {},
  isLoading: true
})

export const useOrganization = () => useContext(OrganizationContext)

export const OrganizationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [currentOrganization, setCurrentOrganization] = useState<Organization | null>(null)
  const [isLoading, setIsLoading] = useState(true)
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
        const response = await docRouterAccountApi.listOrganizations({ userId: appSession.user.id, limit: 50 });

        let filtered: Organization[] = response.organizations;
        const isSysAdmin = appSession.user.role === 'admin';
        const isSettingsPage = pathname.startsWith('/settings/organizations');
        if (isSettingsPage) {
          if (isSysAdmin) {
            filtered = response.organizations;
          } else {
            filtered = response.organizations.filter(org =>
              org.members.some(m => m.user_id === appSession.user.id && m.role === 'admin')
            );
          }
        }
        setOrganizations(filtered);
      } catch (error) {
        console.error('Failed to fetch organizations:', error);
      } finally {
        setIsLoading(false);
        fetchInFlightRef.current = false;
      }
    };

    fetchOrganizations();
  }, [pathname, session, status, docRouterAccountApi]);

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
      // We're on an org-specific page - URL is the source of truth
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

      // Re-apply filtering logic
      let filtered: Organization[] = response.organizations;
      const isSysAdmin = appSession.user.role === 'admin';
      const isSettingsPage = pathname.startsWith('/settings/organizations');

      if (isSettingsPage) {
        if (isSysAdmin) {
          filtered = response.organizations;
        } else {
          filtered = response.organizations.filter(org =>
            org.members.some(m => m.user_id === appSession.user.id && m.role === 'admin')
          );
        }
      }

      setOrganizations(filtered);
    } catch (error) {
      console.error('Failed to refresh organizations:', error);
    }
  }, [pathname, session, docRouterAccountApi])

  return (
    <OrganizationContext.Provider value={{
      organizations,
      currentOrganization,
      setCurrentOrganization,
      switchOrganization,
      refreshOrganizations,
      isLoading
    }}>
      {children}
    </OrganizationContext.Provider>
  )
} 