'use client'

import React, { useState } from 'react'
import type { UserCreate } from '@/types/index'
import { toastActionError } from '@/utils/toastActionError'

import { FormDialog } from '@/components/FormDialog'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'

interface AddUserModalProps {
  open: boolean
  onClose: () => void
  onAdd: (user: UserCreate) => Promise<void>
}

const UserAddModal: React.FC<AddUserModalProps> = ({ open, onClose, onAdd }) => {
  const [formData, setFormData] = useState({ email: '', name: '', password: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<unknown>(null)

  if (!open) return null

  const submit = async () => {
    setLoading(true)
    setError(null)
    try {
      await onAdd(formData)
      setFormData({ email: '', name: '', password: '' })
      onClose()
    } catch (err) {
      console.error('Failed to create user:', err)
      setError(err)
      toastActionError('Failed to create user', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <FormDialog
      title="Create user"
      submitLabel="Create"
      submitDisabled={!formData.email || !formData.name || !formData.password}
      busy={loading}
      error={error}
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <Field>
        <FieldLabel htmlFor="user-email">Email</FieldLabel>
        <Input
          id="user-email"
          type="email"
          value={formData.email}
          onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
          required
          autoFocus
        />
      </Field>
      <Field>
        <FieldLabel htmlFor="user-name">Name</FieldLabel>
        <Input
          id="user-name"
          value={formData.name}
          onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
          required
        />
      </Field>
      <Field>
        <FieldLabel htmlFor="user-password">Password</FieldLabel>
        <Input
          id="user-password"
          type="password"
          value={formData.password}
          onChange={(e) => setFormData((prev) => ({ ...prev, password: e.target.value }))}
          required
        />
      </Field>
    </FormDialog>
  )
}

export default UserAddModal
