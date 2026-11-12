'use client'

import { Pencil, Trash2 } from 'lucide-react'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { isAxiosError } from 'axios'
import type { CreateOrganizationRequest, Organization } from '@docrouter/sdk'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { DataTable, type DataTableColumn, type PaginationModel } from '@/components/data-table'
import { ErrorAlert } from '@/components/ErrorAlert'
import { FormDialog } from '@/components/FormDialog'
import { RowActionsMenu } from '@/components/RowActionsMenu'
import { SearchInput } from '@/components/SearchInput'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useDebounced } from '@/lib/useDebounced'
import { useAppSession } from '@/contexts/AppSessionContext'
import { useOrganization } from '@/contexts/OrganizationContext'
import { DocRouterAccountApi } from '@/utils/api'
import { formatLocalDate } from '@/utils/date'
import { isOrgAdmin, isSysAdmin } from '@/utils/roles'

const orgTypeBadge = (type: Organization['type']) => {
  const label = type.charAt(0).toUpperCase() + type.slice(1)
  if (type === 'enterprise') return <Badge variant="secondary">{label}</Badge>
  if (type === 'team') return <Badge>{label}</Badge>
  return <Badge variant="outline">{label}</Badge>
}

function CreateOrganizationDialog({
  sysAdmin,
  onClose,
  onAdd,
}: {
  sysAdmin: boolean
  onClose: () => void
  onAdd: (body: CreateOrganizationRequest) => Promise<void>
}) {
  const [name, setName] = useState('')
  const [type, setType] = useState<'individual' | 'team' | 'enterprise'>('individual')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!sysAdmin && type === 'enterprise') setType('individual')
  }, [sysAdmin, type])

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await onAdd({ name: name.trim(), type })
      onClose()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <FormDialog
      title="Create organization"
      description="A subscription plan is applied automatically based on organization type."
      submitLabel="Create"
      submitDisabled={!name.trim()}
      busy={busy}
      error={error}
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <Field>
        <FieldLabel htmlFor="org-name">Name</FieldLabel>
        <Input
          id="org-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Organization name"
          autoFocus
          required
        />
      </Field>
      <Field>
        <FieldLabel htmlFor="org-type">Type</FieldLabel>
        <Select value={type} onValueChange={(v) => setType(v as typeof type)}>
          <SelectTrigger id="org-type" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="individual">Individual</SelectItem>
            <SelectItem value="team">Team</SelectItem>
            {sysAdmin ? (
              <SelectItem value="enterprise">Enterprise</SelectItem>
            ) : (
              <SelectItem value="enterprise" disabled>
                Enterprise (admin only)
              </SelectItem>
            )}
          </SelectContent>
        </Select>
        {!sysAdmin ? (
          <FieldDescription>Enterprise organizations can only be created by system administrators.</FieldDescription>
        ) : null}
      </Field>
    </FormDialog>
  )
}

const OrganizationManager: React.FC = () => {
  const { session } = useAppSession()
  const { refreshOrganizations } = useOrganization()
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])

  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [loading, setLoading] = useState(true)
  const [totalCount, setTotalCount] = useState(0)
  const [error, setError] = useState<unknown>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [orgSearch, setOrgSearch] = useState('')
  const [memberSearch, setMemberSearch] = useState('')
  const debouncedOrgSearch = useDebounced(orgSearch.trim())
  const debouncedMemberSearch = useDebounced(memberSearch.trim())
  const [pagination, setPagination] = useState<PaginationModel>({ page: 0, pageSize: 10 })

  const fetchOrganizations = useCallback(async () => {
    setLoading(true)
    try {
      const response = await docRouterAccountApi.listOrganizations({
        skip: pagination.page * pagination.pageSize,
        limit: pagination.pageSize,
        nameSearch: debouncedOrgSearch || undefined,
        memberSearch: debouncedMemberSearch || undefined,
      })
      setOrganizations(response.organizations)
      setTotalCount(response.total_count || 0)
    } catch (err) {
      if (isAxiosError(err)) console.error('Error fetching organizations:', err.response?.data)
    } finally {
      setLoading(false)
    }
  }, [pagination, debouncedOrgSearch, debouncedMemberSearch, docRouterAccountApi])

  useEffect(() => {
    void fetchOrganizations()
  }, [fetchOrganizations])

  useEffect(() => {
    setPagination((p) => ({ ...p, page: 0 }))
  }, [debouncedOrgSearch, debouncedMemberSearch])

  const handleAddOrganization = async (organization: CreateOrganizationRequest) => {
    const isDuplicate = organizations.some(
      (org) => org.name.toLowerCase() === organization.name.toLowerCase(),
    )
    if (isDuplicate) {
      throw new Error(`An organization named "${organization.name}" already exists`)
    }
    await docRouterAccountApi.createOrganization(organization)
    await fetchOrganizations()
    await refreshOrganizations()
  }

  const confirmDelete = async () => {
    if (!deleteId) return
    setDeleteBusy(true)
    setError(null)
    try {
      await docRouterAccountApi.deleteOrganization(deleteId)
      setOrganizations((prev) => prev.filter((o) => o.id !== deleteId))
      setDeleteId(null)
      await refreshOrganizations()
    } catch (err) {
      setError(err)
    } finally {
      setDeleteBusy(false)
    }
  }

  const columns: DataTableColumn<Organization>[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        flex: 1,
        minWidth: 160,
        renderCell: ({ row }) => (
          <Link
            to={`/settings/organizations/${row.id}`}
            className="font-medium text-primary hover:underline"
          >
            {row.name}
          </Link>
        ),
      },
      {
        field: 'type',
        headerName: 'Type',
        width: 130,
        renderCell: ({ row }) => orgTypeBadge(row.type),
      },
      {
        field: 'members',
        headerName: 'Members',
        width: 120,
        sortable: false,
        valueGetter: (_v, row) => row.members?.length ?? 0,
        renderCell: ({ row }) => <span>{row.members?.length ?? 0}</span>,
      },
      {
        field: 'created_at',
        headerName: 'Created',
        width: 140,
        renderCell: ({ row }) => formatLocalDate(row.created_at),
      },
      {
        field: 'actions',
        headerName: '',
        width: 52,
        sortable: false,
        hideable: false,
        resizable: false,
        renderCell: ({ row }) => {
          const canAdmin = isOrgAdmin(row, session) || isSysAdmin(session)
          if (!canAdmin) return null
          return (
            <RowActionsMenu
              label={`Actions for ${row.name}`}
              actions={[
                {
                  label: 'Edit',
                  icon: Pencil,
                  to: `/settings/organizations/${row.id}`,
                },
                {
                  label: 'Delete',
                  icon: Trash2,
                  destructive: true,
                  onSelect: () => setDeleteId(row.id),
                },
              ]}
            />
          )
        },
      },
    ],
    [session],
  )

  const rangeStart = pagination.page * pagination.pageSize + 1
  const rangeEnd = pagination.page * pagination.pageSize + organizations.length

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-lg">Organization management</CardTitle>
        <Button type="button" onClick={() => setIsAddOpen(true)}>
          Add organization
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <ErrorAlert error={error} />
        <div className="flex flex-col gap-3 sm:flex-row">
          <SearchInput
            className="w-full sm:flex-1"
            value={orgSearch}
            onChange={setOrgSearch}
            placeholder="Search by organization name…"
          />
          <SearchInput
            className="w-full sm:flex-1"
            value={memberSearch}
            onChange={setMemberSearch}
            placeholder="Search by member name or email…"
          />
        </div>
        <DataTable
          rows={organizations}
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
            : organizations.length > 0
              ? `Showing ${rangeStart}–${rangeEnd} of ${totalCount} organizations`
              : 'No organizations found'}
        </p>
      </CardContent>

      {isAddOpen ? (
        <CreateOrganizationDialog
          sysAdmin={isSysAdmin(session)}
          onClose={() => setIsAddOpen(false)}
          onAdd={handleAddOrganization}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(deleteId)}
        title="Delete organization"
        message="Are you sure you want to delete this organization? This action cannot be undone."
        confirmLabel="Delete"
        busy={deleteBusy}
        error={deleteBusy ? null : error}
        onConfirm={() => void confirmDelete()}
        onClose={() => setDeleteId(null)}
      />
    </Card>
  )
}

export default OrganizationManager
