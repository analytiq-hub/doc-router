'use client'

import { Copy, Trash2 } from 'lucide-react'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import type { AccessToken, CreateTokenRequest } from '@docrouter/sdk'

import { ErrorAlert } from '@/components/ErrorAlert'
import { FormDialog } from '@/components/FormDialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { DocRouterAccountApi } from '@/utils/api'
import { copyToClipboard } from '@/utils/clipboard'
import { formatLocalDate } from '@/utils/date'

const AccountTokenManager: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])
  const [tokens, setTokens] = useState<AccessToken[]>([])
  const [openModal, setOpenModal] = useState(false)
  const [newTokenName, setNewTokenName] = useState('')
  const [tokenLifetime, setTokenLifetime] = useState('90')
  const [newToken, setNewToken] = useState<AccessToken | null>(null)
  const [showTokenModal, setShowTokenModal] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const loadTokens = useCallback(async () => {
    try {
      const tokensData = await docRouterAccountApi.getAccountTokens()
      setTokens(tokensData)
    } catch (err) {
      console.error('Error fetching tokens:', err)
    }
  }, [docRouterAccountApi])

  useEffect(() => {
    void loadTokens()
  }, [loadTokens])

  const createToken = async () => {
    setBusy(true)
    setError(null)
    try {
      const trimmedName = newTokenName.trim()
      if (tokens.some((token) => token.name === trimmedName)) {
        setError('A token with this name already exists. Please choose a different name.')
        return
      }
      const lifetime = tokenLifetime.trim() === '' ? 0 : parseInt(tokenLifetime, 10)
      const request: CreateTokenRequest = { name: trimmedName, lifetime }
      const response = await docRouterAccountApi.createAccountToken(request)
      setNewToken(response)
      setShowTokenModal(true)
      setOpenModal(false)
      setNewTokenName('')
      setTokenLifetime('90')
    } catch (err) {
      console.error('Error creating token:', err)
      setError('An error occurred while creating the token. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const saveToken = async () => {
    setNewToken(null)
    setShowTokenModal(false)
    await loadTokens()
  }

  const handleDeleteToken = async (tokenId: string) => {
    try {
      await docRouterAccountApi.deleteAccountToken(tokenId)
      setTokens(tokens.filter((token) => token.id !== tokenId))
    } catch (err) {
      console.error('Error deleting token:', err)
      setError('An error occurred while deleting the token. Please try again.')
    }
  }

  return (
    <div className="space-y-4">
      <Button type="button" variant="outline" onClick={() => setOpenModal(true)}>
        Generate account token
      </Button>
      <ErrorAlert error={error} />
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Comment</TableHead>
              <TableHead>Token</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Expiration</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {tokens.map((token) => (
              <TableRow key={token.id}>
                <TableCell>{token.name}</TableCell>
                <TableCell className="font-mono text-xs">
                  {token.token ? `${token.token}…` : '—'}
                </TableCell>
                <TableCell>{formatLocalDate(token.created_at)}</TableCell>
                <TableCell>
                  {token.lifetime
                    ? formatLocalDate(
                        new Date(
                          new Date(token.created_at).getTime() + token.lifetime * 24 * 60 * 60 * 1000,
                        ),
                      )
                    : 'None'}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => void handleDeleteToken(token.id)}
                    aria-label="Delete token"
                  >
                    <Trash2 className="size-4 text-destructive" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {openModal ? (
        <FormDialog
          title="Generate account token"
          submitLabel="Generate"
          submitDisabled={!newTokenName.trim()}
          busy={busy}
          error={error}
          onSubmit={() => void createToken()}
          onClose={() => setOpenModal(false)}
        >
          <Field>
            <FieldLabel htmlFor="token-comment">Comment</FieldLabel>
            <Input
              id="token-comment"
              value={newTokenName}
              onChange={(e) => setNewTokenName(e.target.value)}
              placeholder="What is this token for?"
              autoFocus
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="token-lifetime">Lifetime (days)</FieldLabel>
            <Input
              id="token-lifetime"
              type="number"
              value={tokenLifetime}
              onChange={(e) => setTokenLifetime(e.target.value)}
              placeholder="Leave empty for no expiration"
            />
            <FieldDescription>Default is 90 days when left at 90.</FieldDescription>
          </Field>
        </FormDialog>
      ) : null}

      <Dialog open={showTokenModal} onOpenChange={(open) => !open && void saveToken()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New token created</DialogTitle>
            <DialogDescription>Copy your new token. It is shown only once.</DialogDescription>
          </DialogHeader>
          <div className="flex items-center justify-between gap-2 rounded-md bg-muted p-2">
            <span className="min-w-0 break-all font-mono text-sm">{newToken?.token}</span>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={() => newToken?.token && void copyToClipboard(newToken.token)}
              aria-label="Copy token"
            >
              <Copy className="size-4" />
            </Button>
          </div>
          <DialogFooter>
            <Button type="button" onClick={() => void saveToken()}>
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default AccountTokenManager
