'use client'

import React, { useEffect, useMemo, useState } from 'react'
import type { User } from '@docrouter/sdk'
import { toast } from 'sonner'

import { FormDialog } from '@/components/FormDialog'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { DocRouterAccountApi } from '@/utils/api'
import { toastActionError } from '@/utils/toastActionError'

interface UserAddToOrgModalProps {
  open: boolean
  onClose: () => void
  onAdd: (userId: string, user?: User) => Promise<void>
  organizationId: string
  currentMembers: string[]
}

const UserAddToOrgModal: React.FC<UserAddToOrgModalProps> = ({
  open,
  onClose,
  onAdd,
  organizationId,
  currentMembers,
}) => {
  const [email, setEmail] = useState('')
  const [searchResults, setSearchResults] = useState<User[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])

  useEffect(() => {
    if (!open) {
      setEmail('')
      setSearchResults([])
      setError(null)
    }
  }, [open])

  useEffect(() => {
    if (!email) {
      setSearchResults([])
      return
    }
    const timeoutId = setTimeout(() => {
      void docRouterAccountApi
        .listUsers({ limit: 100 })
        .then((response) => {
          const filteredUsers = response.users.filter(
            (user) =>
              !currentMembers.includes(user.id) &&
              (user.email.toLowerCase().includes(email.toLowerCase()) ||
                (user.name && user.name.toLowerCase().includes(email.toLowerCase()))),
          )
          setSearchResults(filteredUsers)
        })
        .catch((err) => console.error('Failed to search users:', err))
    }, 500)
    return () => clearTimeout(timeoutId)
  }, [email, currentMembers, docRouterAccountApi])

  if (!open) return null

  const handleSelectUser = async (user: User) => {
    try {
      await onAdd(user.id, user)
      onClose()
    } catch (err) {
      toastActionError('Failed to add user', err)
    }
  }

  const submit = async () => {
    if (!email) return
    setIsSubmitting(true)
    setError(null)
    try {
      const existingUser = searchResults.find((user) => user.email.toLowerCase() === email.toLowerCase())
      if (existingUser) {
        await onAdd(existingUser.id, existingUser)
      } else {
        await docRouterAccountApi.createInvitation({
          email,
          organization_id: organizationId,
        })
        toast.success('Invitation sent successfully')
      }
      onClose()
      setEmail('')
    } catch (err) {
      console.error('Failed to add user:', err)
      setError(err)
      toastActionError('Failed to add user', err)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <FormDialog
      title="Add user"
      submitLabel={isSubmitting ? 'Adding…' : 'Add user'}
      submitDisabled={!email || isSubmitting}
      busy={isSubmitting}
      error={error}
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <Field>
        <FieldLabel htmlFor="add-org-user-email">Email</FieldLabel>
        <Input
          id="add-org-user-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email address"
          autoFocus
        />
        {searchResults.length > 0 ? (
          <div className="mt-2 max-h-96 overflow-y-auto divide-y rounded-md border">
            {searchResults.map((user) => (
              <button
                key={user.id}
                type="button"
                onClick={() => void handleSelectUser(user)}
                className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-muted/60"
              >
                <div>
                  <div className="font-medium">{user.name || 'Unnamed user'}</div>
                  <div className="text-sm text-muted-foreground">{user.email}</div>
                </div>
                <span className="text-primary text-sm">Add</span>
              </button>
            ))}
          </div>
        ) : null}
      </Field>
    </FormDialog>
  )
}

export default UserAddToOrgModal
