'use client'

import { Plus, Trash2 } from 'lucide-react'
import React, { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { formatLocalDate } from '@/utils/date'

interface AccessToken {
  id: string
  name: string
  token: string
  created_at: string
}

export default function AccessTokenManager() {
  const [tokens, setTokens] = useState<AccessToken[]>([])
  const [newTokenName, setNewTokenName] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void fetchTokens()
  }, [])

  const fetchTokens = async () => {
    try {
      const response = await fetch('/api/access-tokens')
      if (response.ok) {
        const data = await response.json()
        setTokens(data)
      }
    } catch (error) {
      console.error('Error fetching tokens:', error)
    } finally {
      setLoading(false)
    }
  }

  const createToken = async () => {
    if (!newTokenName.trim()) return
    try {
      const response = await fetch('/api/access-tokens', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newTokenName }),
      })
      if (response.ok) {
        const newToken = await response.json()
        setTokens([...tokens, newToken])
        setNewTokenName('')
      }
    } catch (error) {
      console.error('Error creating token:', error)
    }
  }

  const deleteToken = async (tokenId: string) => {
    try {
      const response = await fetch(`/api/access-tokens/${tokenId}`, { method: 'DELETE' })
      if (response.ok) {
        setTokens(tokens.filter((token) => token.id !== tokenId))
      }
    } catch (error) {
      console.error('Error deleting token:', error)
    }
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field className="min-w-[12rem] flex-1">
          <FieldLabel htmlFor="access-token-name">Token name</FieldLabel>
          <Input
            id="access-token-name"
            value={newTokenName}
            onChange={(e) => setNewTokenName(e.target.value)}
          />
        </Field>
        <Button type="button" onClick={() => void createToken()} disabled={!newTokenName.trim()}>
          <Plus className="size-4" />
          Create token
        </Button>
      </div>

      <div className="space-y-2">
        {tokens.map((token) => (
          <div
            key={token.id}
            className="flex items-center justify-between rounded-lg border bg-card p-4 shadow-sm"
          >
            <div>
              <p className="font-medium">{token.name}</p>
              <p className="text-sm text-muted-foreground">{formatLocalDate(token.created_at)}</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => void deleteToken(token.id)}
              aria-label="Delete token"
            >
              <Trash2 className="size-4 text-destructive" />
            </Button>
          </div>
        ))}
      </div>
    </div>
  )
}
