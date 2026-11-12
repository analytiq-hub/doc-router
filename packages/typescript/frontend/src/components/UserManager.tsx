'use client'

import { Pencil, Trash2 } from 'lucide-react'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { isAxiosError } from 'axios'
import type { User, UserCreate } from '@docrouter/sdk'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { DataTable, type DataTableColumn, type PaginationModel } from '@/components/data-table'
import { RowActionsMenu } from '@/components/RowActionsMenu'
import { SearchInput } from '@/components/SearchInput'
import UserAddModal from '@/components/UserAddModal'
import UserInviteModal from '@/components/UserInviteModal'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useDebounced } from '@/lib/useDebounced'
import { DocRouterAccountApi } from '@/utils/api'
import { signOut } from '@/utils/signOut'
import { useAppSession } from '@/utils/useAppSession'

const UserManager: React.FC = () => {
  const session = useAppSession()
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])

  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [totalCount, setTotalCount] = useState(0)
  const [userToDelete, setUserToDelete] = useState<User | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [pagination, setPagination] = useState<PaginationModel>({ page: 0, pageSize: 10 })
  const [searchQuery, setSearchQuery] = useState('')
  const debouncedSearch = useDebounced(searchQuery.trim())
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [isInviteOpen, setIsInviteOpen] = useState(false)

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    try {
      const response = await docRouterAccountApi.listUsers({
        skip: pagination.page * pagination.pageSize,
        limit: pagination.pageSize,
        search_name: debouncedSearch || undefined,
      })
      setUsers(response.users)
      setTotalCount(response.total_count)
    } catch (error) {
      if (isAxiosError(error)) console.error('Error fetching users:', error.response?.data)
    } finally {
      setLoading(false)
    }
  }, [pagination, debouncedSearch, docRouterAccountApi])

  useEffect(() => {
    void fetchUsers()
  }, [fetchUsers])

  useEffect(() => {
    setPagination((p) => ({ ...p, page: 0 }))
  }, [debouncedSearch])

  const confirmDelete = async () => {
    if (!userToDelete) return
    setDeleteBusy(true)
    try {
      await docRouterAccountApi.deleteUser(userToDelete.id)
      if (session?.session?.user?.id === userToDelete.id) {
        void signOut()
        return
      }
      await fetchUsers()
      setUserToDelete(null)
    } catch (error) {
      if (isAxiosError(error)) {
        alert(error.response?.data?.detail || 'Failed to delete user')
      }
    } finally {
      setDeleteBusy(false)
    }
  }

  const handleAddUser = async (userData: UserCreate) => {
    await docRouterAccountApi.createUser(userData)
    await fetchUsers()
  }

  const columns: DataTableColumn<User>[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'User',
        flex: 1,
        minWidth: 240,
        renderCell: ({ row }) => (
          <Link
            to={`/settings/account/users/${row.id}`}
            className="text-primary hover:underline"
          >
            <span className="font-medium">{row.name || 'Unnamed user'}</span>
            <span className="ml-2 text-muted-foreground">({row.email})</span>
          </Link>
        ),
      },
      {
        field: 'is_sysadmin',
        headerName: 'Sysadmin',
        width: 100,
        renderCell: ({ row }) => (
          <span className={row.is_sysadmin ? 'text-primary font-medium' : 'text-muted-foreground'}>
            {row.is_sysadmin ? 'Yes' : 'No'}
          </span>
        ),
      },
      {
        field: 'email_verified',
        headerName: 'Verified',
        width: 100,
        renderCell: ({ row }) => (
          <span className={row.email_verified ? 'text-green-600' : 'text-muted-foreground'}>
            {row.email_verified ? 'Yes' : 'No'}
          </span>
        ),
      },
      {
        field: 'actions',
        headerName: '',
        width: 52,
        sortable: false,
        hideable: false,
        resizable: false,
        renderCell: ({ row }) => (
          <RowActionsMenu
            label={`Actions for ${row.email}`}
            actions={[
              { label: 'Edit', icon: Pencil, to: `/settings/account/users/${row.id}` },
              {
                label: 'Delete',
                icon: Trash2,
                destructive: true,
                onSelect: () => setUserToDelete(row),
              },
            ]}
          />
        ),
      },
    ],
    [],
  )

  const rangeStart = pagination.page * pagination.pageSize + 1
  const rangeEnd = pagination.page * pagination.pageSize + users.length

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-lg">User management</CardTitle>
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => setIsAddOpen(true)}>
            Add user
          </Button>
          <Button type="button" variant="secondary" onClick={() => setIsInviteOpen(true)}>
            Invite user
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <SearchInput
          className="w-full max-w-md"
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Search users by name or email…"
        />
        <DataTable
          rows={users}
          columns={columns}
          loading={loading}
          rowCount={totalCount}
          paginationModel={pagination}
          onPaginationModelChange={setPagination}
          pageSizeOptions={[10, 25, 50]}
        />
        <p className="text-sm text-muted-foreground">
          {loading
            ? 'Loading…'
            : users.length > 0
              ? `Showing ${rangeStart}–${rangeEnd} of ${totalCount} users`
              : 'No users found'}
        </p>
      </CardContent>

      {isAddOpen ? (
        <UserAddModal open onClose={() => setIsAddOpen(false)} onAdd={handleAddUser} />
      ) : null}

      {isInviteOpen ? (
        <UserInviteModal
          open
          onClose={() => setIsInviteOpen(false)}
          onInvited={() => void fetchUsers()}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(userToDelete)}
        title="Delete user"
        message={
          userToDelete
            ? `Are you sure you want to delete "${userToDelete.email}"? This action cannot be undone.`
            : ''
        }
        confirmLabel="Delete user"
        busy={deleteBusy}
        onConfirm={() => void confirmDelete()}
        onClose={() => setUserToDelete(null)}
      />
    </Card>
  )
}

export default UserManager
