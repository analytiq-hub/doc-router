'use client'

import { useEffect, useMemo, useState } from 'react'

import { DocRouterAccountApi } from '@/utils/api'

export function useAccountUserName(userId: string | undefined, enabled: boolean) {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])
  const [createdByName, setCreatedByName] = useState<string | null>(null)
  const [isLoadingName, setIsLoadingName] = useState(false)

  useEffect(() => {
    if (!enabled || !userId) {
      setCreatedByName(null)
      setIsLoadingName(false)
      return
    }
    let cancelled = false
    setIsLoadingName(true)
    void docRouterAccountApi
      .getUser(userId)
      .then((user) => {
        if (!cancelled) setCreatedByName(user.name || null)
      })
      .catch((error) => {
        console.error('Error fetching user name:', error)
        if (!cancelled) setCreatedByName(null)
      })
      .finally(() => {
        if (!cancelled) setIsLoadingName(false)
      })
    return () => {
      cancelled = true
    }
  }, [enabled, userId, docRouterAccountApi])

  return { createdByName, isLoadingName }
}
