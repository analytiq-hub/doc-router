'use client'

import React, { createContext, useCallback, useContext, useLayoutEffect, useRef, useState } from 'react'
import { AppSession } from '@/types/AppSession'
import { invalidateSessionCache, setGlobalSession } from '@/utils/api'

interface AppSessionContextType {
  session: AppSession | null
  status: 'loading' | 'authenticated' | 'unauthenticated'
  apiAccessToken: string | null
  setApiAccessToken: (token: string | null) => void
  refreshSession: () => Promise<void>
}

const AppSessionContext = createContext<AppSessionContextType>({
  session: null,
  status: 'loading',
  apiAccessToken: null,
  setApiAccessToken: () => {},
  refreshSession: async () => {},
})

export const useAppSession = () => useContext(AppSessionContext)

export const AppSessionProvider: React.FC<{
  children: React.ReactNode
  initialSession?: AppSession | null
}> = ({ children, initialSession = null }) => {
  const [session, setSession] = useState<AppSession | null>(initialSession)
  const [status, setStatus] = useState<'loading' | 'authenticated' | 'unauthenticated'>(
    initialSession ? 'authenticated' : 'loading',
  )
  const [apiAccessToken, setApiAccessToken] = useState<string | null>(
    initialSession?.apiAccessToken ?? null,
  )
  const lastUpdateRef = useRef<number>(0)

  const applySession = useCallback((next: AppSession | null) => {
    setSession(next)
    setStatus(next ? 'authenticated' : 'unauthenticated')
    setApiAccessToken(next?.apiAccessToken ?? null)
    setGlobalSession(next)
    lastUpdateRef.current = Date.now()
  }, [])

  const refreshSession = useCallback(async () => {
    setStatus('loading')
    invalidateSessionCache()
    const response = await fetch('/api/auth/session')
    if (!response.ok) {
      applySession(null)
      return
    }
    const data = await response.json()
    applySession((data.session as AppSession | null) ?? null)
  }, [applySession])

  const initialSessionKey = initialSession
    ? `${initialSession.user.id}:${initialSession.apiAccessToken}`
    : ''

  useLayoutEffect(() => {
    applySession(initialSession)
  }, [initialSessionKey, initialSession, applySession])

  useLayoutEffect(() => {
    if (initialSession) {
      return
    }
    void refreshSession()
  }, [initialSession, refreshSession])

  return (
    <AppSessionContext.Provider value={{
      session,
      status,
      apiAccessToken,
      setApiAccessToken,
      refreshSession,
    }}>
      {children}
    </AppSessionContext.Provider>
  )
}
