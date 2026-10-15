'use client'

import React, { createContext, useContext, useState, useLayoutEffect, useRef } from 'react'
import { useSession } from 'next-auth/react'
import { AppSession } from '@/types/AppSession'
import { setGlobalSession } from '@/utils/api'

interface AppSessionContextType {
  session: AppSession | null
  status: 'loading' | 'authenticated' | 'unauthenticated'
  apiAccessToken: string | null
  setApiAccessToken: (token: string | null) => void
}

const AppSessionContext = createContext<AppSessionContextType>({
  session: null,
  status: 'loading',
  apiAccessToken: null,
  setApiAccessToken: () => {}
})

export const useAppSession = () => useContext(AppSessionContext)

export const AppSessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { data: session, status } = useSession()
  const [cachedSession, setCachedSession] = useState<AppSession | null>(null)
  const [cachedStatus, setCachedStatus] = useState<'loading' | 'authenticated' | 'unauthenticated'>('loading')
  const [apiAccessToken, setApiAccessToken] = useState<string | null>(null)
  const lastUpdateRef = useRef<number>(0)
  
  // Only update cached session if it actually changed or after 1 minute
  useLayoutEffect(() => {
    const now = Date.now()
    const hasChanged = JSON.stringify(session) !== JSON.stringify(cachedSession) || status !== cachedStatus
    const isStale = now - lastUpdateRef.current > 60000 // 1 minute
    
    if (hasChanged || isStale) {
      const appSession = session as AppSession | null
      setCachedSession(appSession)
      setCachedStatus(status)
      lastUpdateRef.current = now
      
      // Update API access token when session changes
      if (appSession?.apiAccessToken) {
        setApiAccessToken(appSession.apiAccessToken)
      } else {
        setApiAccessToken(null)
      }
      
      // Sync before child effects so API clients use the current session token
      setGlobalSession(appSession)
    }
  }, [session, status, cachedSession, cachedStatus])
  
  return (
    <AppSessionContext.Provider value={{
      session: cachedSession,
      status: cachedStatus,
      apiAccessToken,
      setApiAccessToken
    }}>
      {children}
    </AppSessionContext.Provider>
  )
}