'use client'

import React, { useState, useEffect, useMemo } from 'react'
import { useRouter } from '@/utils/appRouter'
import { DocRouterAccountApi } from '@/utils/api'
import { User, UserUpdate } from '@docrouter/sdk'
import { signOut } from '@/utils/signOut'
import { useAppSession } from '@/contexts/AppSessionContext'
import { isSysAdmin } from '@/utils/roles'
import { toast } from 'react-toastify'
import { toastActionError } from '@/utils/toastActionError'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { FormDialog } from '@/components/FormDialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'

interface UserEditProps {
  userId: string
}

const UserEdit: React.FC<UserEditProps> = ({ userId }) => {
  const router = useRouter()
  const { session } = useAppSession()
  const [user, setUser] = useState<User | null>(null)
  const [name, setName] = useState('')
  const [isSysadmin, setIsSysadmin] = useState(false)
  const [emailVerified, setEmailVerified] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false)
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordModalError, setPasswordModalError] = useState<string | null>(null)
  const [passwordBusy, setPasswordBusy] = useState(false)

  const [originalValues, setOriginalValues] = useState({
    name: '',
    isSysadmin: false,
    emailVerified: false,
  })

  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])

  const hasChanges = () =>
    name !== originalValues.name ||
    isSysadmin !== originalValues.isSysadmin ||
    emailVerified !== originalValues.emailVerified

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const userData = await docRouterAccountApi.getUser(userId)
        setUser(userData)
        setName(userData.name || '')
        setIsSysadmin(userData.is_sysadmin)
        setEmailVerified(userData.email_verified || false)
        setOriginalValues({
          name: userData.name || '',
          isSysadmin: userData.is_sysadmin,
          emailVerified: userData.email_verified || false,
        })
      } catch (fetchError) {
        setError('Failed to load user')
        console.error('Error fetching user:', fetchError)
      }
    }

    void fetchUser()
  }, [userId, docRouterAccountApi])

  const handlePasswordUpdate = async (password: string) => {
    await docRouterAccountApi.updateUser(userId, { password })
    setSuccess(true)
  }

  const submitPasswordChange = async () => {
    setPasswordModalError(null)
    if (newPassword !== confirmPassword) {
      setPasswordModalError('Passwords do not match')
      return
    }
    setPasswordBusy(true)
    try {
      await handlePasswordUpdate(newPassword)
      setNewPassword('')
      setConfirmPassword('')
      setIsPasswordModalOpen(false)
    } catch (updateError) {
      console.error('Password update failed:', updateError)
      setPasswordModalError('Failed to update password')
      toastActionError('Failed to update password', updateError)
    } finally {
      setPasswordBusy(false)
    }
  }

  const handleSubmit = async () => {
    setError(null)
    setSuccess(false)

    try {
      const update: UserUpdate = {
        name: name || undefined,
        is_sysadmin: isSysadmin,
        email_verified: emailVerified,
      }

      await docRouterAccountApi.updateUser(userId, update)
      setSuccess(true)

      setOriginalValues({
        name: name || '',
        isSysadmin,
        emailVerified,
      })
    } catch (updateError) {
      setError('Failed to update user')
      console.error('Error updating user:', updateError)
    }
  }

  const handleDeleteUser = async () => {
    try {
      await docRouterAccountApi.deleteUser(userId)
      setIsDeleteModalOpen(false)

      if (session?.user?.id === userId) {
        void signOut()
      } else {
        router.push('/settings/account/users')
      }
    } catch (deleteError) {
      setError('Failed to delete user')
      console.error('Error deleting user:', deleteError)
    }
  }

  const handleSendVerification = async () => {
    try {
      await docRouterAccountApi.sendVerificationEmail(userId)
      setSuccess(true)
      toast.success('Verification email sent successfully')
    } catch (sendError) {
      setError('Failed to send verification email')
      console.error('Error sending verification email:', sendError)
    }
  }

  if (!user) {
    return <p className="text-sm text-muted-foreground">Loading…</p>
  }

  const isAdmin = isSysAdmin(session)

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-foreground">Edit user profile</h2>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={() => router.push('/settings/account/users')}>
            Cancel
          </Button>
          <Button type="button" onClick={() => void handleSubmit()} disabled={!hasChanges()}>
            Save changes
          </Button>
        </div>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {success ? (
        <Alert variant="success">
          <AlertDescription>User updated successfully.</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Account</CardTitle>
        </CardHeader>
        <CardContent>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="user-email">Email</FieldLabel>
              <Input id="user-email" type="email" value={user.email} disabled readOnly />
            </Field>

            <Field>
              <FieldLabel htmlFor="user-name">Name</FieldLabel>
              <Input
                id="user-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>

            {isAdmin ? (
              <>
                <Field orientation="horizontal" className="justify-between">
                  <div className="space-y-0.5">
                    <FieldLabel htmlFor="user-sysadmin">Platform sysadmin</FieldLabel>
                  </div>
                  <Switch
                    id="user-sysadmin"
                    checked={isSysadmin}
                    onCheckedChange={(checked) => setIsSysadmin(checked === true)}
                  />
                </Field>

                <Field orientation="horizontal" className="flex-wrap items-center justify-between gap-3">
                  <p className="text-sm font-medium text-foreground">Email verified</p>
                  <Switch
                    id="user-email-verified"
                    checked={emailVerified}
                    onCheckedChange={(checked) => setEmailVerified(checked === true)}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full sm:ml-auto sm:w-auto"
                    onClick={() => void handleSendVerification()}
                    disabled={originalValues.emailVerified}
                  >
                    Send verification email
                  </Button>
                </Field>
              </>
            ) : null}

            {user.has_password ? (
              <div className="border-t pt-4">
                <Button type="button" variant="outline" onClick={() => setIsPasswordModalOpen(true)}>
                  Change password
                </Button>
              </div>
            ) : null}
          </FieldGroup>
        </CardContent>
      </Card>

      <div className="border-t pt-4">
        <Button type="button" variant="outline" onClick={() => setIsDeleteModalOpen(true)}>
          Delete user
        </Button>
        <FieldDescription className="mt-2">This action cannot be undone.</FieldDescription>
      </div>

      {isPasswordModalOpen ? (
        <FormDialog
          title="Change password"
          submitLabel="Update password"
          submitDisabled={!newPassword || !confirmPassword}
          busy={passwordBusy}
          error={passwordModalError}
          onSubmit={() => void submitPasswordChange()}
          onClose={() => {
            setIsPasswordModalOpen(false)
            setNewPassword('')
            setConfirmPassword('')
            setPasswordModalError(null)
          }}
        >
          <Field>
            <FieldLabel htmlFor="new-password">New password</FieldLabel>
            <Input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoFocus
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="confirm-password">Confirm password</FieldLabel>
            <Input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </Field>
        </FormDialog>
      ) : null}

      <ConfirmDialog
        open={isDeleteModalOpen}
        title="Delete user"
        message="Are you sure you want to delete this user? This action cannot be undone."
        confirmLabel="Delete user"
        onConfirm={() => void handleDeleteUser()}
        onClose={() => setIsDeleteModalOpen(false)}
      />
    </div>
  )
}

export default UserEdit
