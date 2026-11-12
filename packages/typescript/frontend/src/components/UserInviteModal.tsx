'use client'

import debounce from 'lodash/debounce'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import type { Organization } from '@docrouter/sdk'
import { toast } from 'react-toastify'

import { FormDialog } from '@/components/FormDialog'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { DocRouterAccountApi } from '@/utils/api'
import { toastActionError } from '@/utils/toastActionError'

interface UserInviteModalProps {
  open: boolean
  onClose: () => void
  onInvited: () => void
}

const UserInviteModal: React.FC<UserInviteModalProps> = ({ open, onClose, onInvited }) => {
  const [email, setEmail] = useState('')
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Organization[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])

  const searchOrganizations = useCallback(
    (query: string) => {
      if (!query) {
        setSearchResults([])
        return
      }
      setIsSearching(true)
      void docRouterAccountApi
        .listOrganizations({ nameSearch: query, limit: 20 })
        .then((response) => {
          setSearchResults(
            response.organizations.filter((org) => org.type === 'team' || org.type === 'enterprise'),
          )
        })
        .catch((err) => {
          console.error('Failed to search organizations:', err)
          toastActionError('Failed to search organizations', err)
        })
        .finally(() => setIsSearching(false))
    },
    [docRouterAccountApi],
  )

  useEffect(() => {
    const debouncedSearch = debounce(searchOrganizations, 300)
    debouncedSearch(searchQuery)
    return () => debouncedSearch.cancel()
  }, [searchQuery, searchOrganizations])

  useEffect(() => {
    if (!open) {
      setEmail('')
      setSelectedOrg(null)
      setSearchQuery('')
      setError(null)
    }
  }, [open])

  if (!open) return null

  const submit = async () => {
    if (!email) {
      toast.error('Please enter an email address')
      return
    }
    setIsSubmitting(true)
    setError(null)
    try {
      await docRouterAccountApi.createInvitation({
        email,
        organization_id: selectedOrg?.id,
      })
      toast.success('Invitation sent successfully')
      onInvited()
      onClose()
    } catch (err) {
      console.error('Invitation error:', err)
      setError(err)
      toastActionError('Failed to send invitation', err)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <FormDialog
      title="Invite user"
      submitLabel={isSubmitting ? 'Sending…' : 'Send invitation'}
      submitDisabled={!email || isSubmitting}
      busy={isSubmitting}
      error={error}
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <Field>
        <FieldLabel htmlFor="invite-email">Email</FieldLabel>
        <Input
          id="invite-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email address"
          required
        />
      </Field>
      <Field>
        <FieldLabel htmlFor="invite-org-search">Add to organization (optional)</FieldLabel>
        <Input
          id="invite-org-search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search organizations…"
        />
        {searchQuery ? (
          <p className="mt-2 max-h-40 overflow-y-auto rounded-md border text-sm">
            {isSearching ? (
              <span className="block p-2 text-muted-foreground">Searching…</span>
            ) : searchResults.length > 0 ? (
              searchResults.map((org) => (
                <button
                  key={org.id}
                  type="button"
                  onClick={() => {
                    setSelectedOrg(org)
                    setSearchQuery('')
                  }}
                  className="flex w-full items-center justify-between border-b px-3 py-2 text-left last:border-0 hover:bg-muted/60"
                >
                  <span>{org.name}</span>
                  <span className="text-xs text-muted-foreground">{org.type}</span>
                </button>
              ))
            ) : (
              <span className="block p-2 text-muted-foreground">No organizations found</span>
            )}
          </p>
        ) : null}
        {selectedOrg ? (
          <div className="mt-2 flex items-center justify-between rounded-md bg-muted/50 px-3 py-2 text-sm">
            <span>{selectedOrg.name}</span>
            <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedOrg(null)}>
              Remove
            </Button>
          </div>
        ) : (
          <FieldDescription>Only team and enterprise organizations are listed.</FieldDescription>
        )}
      </Field>
    </FormDialog>
  )
}

export default UserInviteModal
