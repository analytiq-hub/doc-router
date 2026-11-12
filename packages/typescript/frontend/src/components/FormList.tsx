'use client'

import { Copy, Download, Info, Pencil, PencilLine, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import type { Form, Tag } from '@docrouter/sdk'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { DataTable, type DataTableColumn, type PaginationModel, type SortModel } from '@/components/data-table'
import { ErrorAlert } from '@/components/ErrorAlert'
import {
  activeFields,
  type FilterField,
  FilterBuilder,
  type FilterItem,
  isActiveFilter,
  withFilterFields,
} from '@/components/FilterBuilder'
import { FormDialog } from '@/components/FormDialog'
import { PropertiesDialog } from '@/components/PropertiesDialog'
import { RowActionsMenu } from '@/components/RowActionsMenu'
import { SearchInput } from '@/components/SearchInput'
import { TagCell } from '@/components/TagCell'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { useDebounced } from '@/lib/useDebounced'
import { shortName } from '@/lib/shortName'
import { useInvalidateOrgLists, useOrgForms, useOrgTags } from '@/api/orgQueries'
import { DocRouterAccountApi, DocRouterOrgApi } from '@/utils/api'
import { formatLocalDate } from '@/utils/date'
import { useOrgCapability } from '@/hooks/useOrgPermissions'
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities'

const jsonStringifyForQuery = (value: unknown): string =>
  JSON.stringify(value, (_key, v) => (v instanceof Date ? v.toISOString() : v))

const NON_SORT_FIELDS = new Set(['form_version', 'tag_ids', 'actions'])

type FormRow = Form & { created_by?: string }

function FormNameDialog({
  organizationId,
  originalName,
  isCloning,
  onClose,
  onSubmit,
}: {
  organizationId: string
  originalName: string
  isCloning: boolean
  onClose: () => void
  onSubmit: (name: string) => Promise<void>
}) {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])
  const [name, setName] = useState(originalName)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [existingNames, setExistingNames] = useState<string[]>([])

  useEffect(() => {
    setName(originalName)
  }, [originalName])

  useEffect(() => {
    void docRouterOrgApi.listForms({ skip: 0, limit: 100 }).then((res) => {
      setExistingNames(res.forms.map((f) => f.name.toLowerCase()))
    })
  }, [docRouterOrgApi])

  const save = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Form name cannot be empty')
      return
    }
    if (
      trimmed.toLowerCase() !== originalName.toLowerCase() &&
      existingNames.includes(trimmed.toLowerCase())
    ) {
      setError('A form with this name already exists')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await onSubmit(trimmed)
      toast.success(isCloning ? 'Form cloned' : 'Form renamed')
      onClose()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <FormDialog
      title={isCloning ? 'Clone form' : 'Rename form'}
      submitLabel={isCloning ? 'Clone' : 'Save'}
      submitDisabled={!name.trim() || (!isCloning && name.trim() === originalName)}
      busy={busy}
      error={error}
      onSubmit={() => void save()}
      onClose={onClose}
    >
      <Field>
        <FieldLabel htmlFor="form-name">Name</FieldLabel>
        <Input id="form-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
      </Field>
    </FormDialog>
  )
}

function FormPropertiesPanel({ form, tagsById, onClose }: { form: FormRow; tagsById: Map<string, Tag>; onClose: () => void }) {
  const [createdByName, setCreatedByName] = useState<string | null>(null)
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])
  const tagNames = (form.tag_ids ?? []).map((id) => tagsById.get(id)?.name).filter(Boolean).join(', ') || '—'

  useEffect(() => {
    let cancelled = false
    if (!form.created_by) {
      setCreatedByName(null)
      return
    }
    void docRouterAccountApi
      .getUser(form.created_by)
      .then((user) => {
        if (!cancelled) setCreatedByName(user.name ?? form.created_by!)
      })
      .catch(() => {
        if (!cancelled) setCreatedByName(form.created_by!)
      })
    return () => {
      cancelled = true
    }
  }, [form.created_by, docRouterAccountApi])

  return (
    <PropertiesDialog
      title={form.name}
      description="Form properties"
      onClose={onClose}
      columns={2}
      properties={[
        { label: 'Name', value: form.name },
        { label: 'Version', value: `v${form.form_version}` },
        { label: 'Tags', value: tagNames },
        { label: 'Created', value: form.created_at ? formatLocalDate(String(form.created_at)) : '—' },
        { label: 'Created by', value: form.created_by ? (createdByName ?? '…') : '—' },
        { label: 'Form ID', value: <span className="font-mono text-xs">{form.form_id}</span> },
        { label: 'Revision ID', value: <span className="font-mono text-xs">{form.form_revid}</span> },
      ]}
    />
  )
}

const FormList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const { hasCapability: canConfigWrite } = useOrgCapability(organizationId, CAP_CONFIG_WRITE)
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])

  const [pagination, setPagination] = useState<PaginationModel>({ page: 0, pageSize: 25 })
  const [sortModel, setSortModel] = useState<SortModel>([{ field: 'created_at', sort: 'desc' }])
  const [filters, setFilters] = useState<FilterItem[]>([])
  const [filterRequest, setFilterRequest] = useState<{ field: string } | null>(null)
  const [search, setSearch] = useState('')
  const nameSearch = useDebounced(search.trim())
  const activeFilters = filters.filter(isActiveFilter)
  const sortForApi = sortModel.filter((s) => !NON_SORT_FIELDS.has(s.field))
  const formsQuery = useOrgForms(organizationId, {
    skip: pagination.page * pagination.pageSize,
    limit: pagination.pageSize,
    name_search: nameSearch || undefined,
    sort: sortForApi.length ? jsonStringifyForQuery(sortForApi) : undefined,
    filters: activeFilters.length ? jsonStringifyForQuery({ items: activeFilters }) : undefined,
  })
  const tagsQuery = useOrgTags(organizationId, { skip: 0, limit: 100 })
  const invalidate = useInvalidateOrgLists(organizationId)
  const availableTags = tagsQuery.data?.tags ?? []
  const tagsById = useMemo(() => new Map(availableTags.map((t) => [t.id, t])), [availableTags])

  const [viewing, setViewing] = useState<FormRow | null>(null)
  const [nameEdit, setNameEdit] = useState<{ form: Form; cloning: boolean } | null>(null)
  const [deleting, setDeleting] = useState<Form | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState<unknown>(null)

  const editPath = (form: Form) => `/orgs/${organizationId}/forms/${form.form_revid}`

  const handleNameSubmit = async (newName: string) => {
    if (!nameEdit) return
    const { form, cloning } = nameEdit
    const formConfig = { name: newName, response_format: form.response_format }
    if (cloning) {
      await docRouterOrgApi.createForm(formConfig)
    } else {
      await docRouterOrgApi.updateForm({ formId: form.form_id, form: formConfig })
    }
    await invalidate.forms()
  }

  const handleDownload = (form: Form) => {
    try {
      const formJson = JSON.stringify(form.response_format.json_formio, null, 2)
      const blob = new Blob([formJson], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${form.name.replace(/\s+/g, '_')}_form.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('Download started')
    } catch {
      toast.error('Failed to download form')
    }
  }

  const confirmDelete = async () => {
    if (!deleting) return
    setDeleteBusy(true)
    setDeleteError(null)
    try {
      await docRouterOrgApi.deleteForm({ formId: deleting.form_id })
      toast.success('Form deleted')
      setDeleting(null)
      void invalidate.forms()
    } catch (error) {
      setDeleteError(error)
    } finally {
      setDeleteBusy(false)
    }
  }

  const filterFields: FilterField[] = useMemo(
    () => [
      { field: 'name', label: 'Name', kind: 'text' as const },
      { field: 'form_version', label: 'Version', kind: 'text' as const },
      {
        field: 'tag_ids',
        label: 'Tags',
        kind: 'tag' as const,
        single: true,
        options: availableTags.map((t) => ({ value: t.name, label: t.name })),
      },
      { field: 'created_at', label: 'Created', kind: 'date' as const },
    ],
    [availableTags],
  )

  const columns: DataTableColumn<Form>[] = [
    {
      field: 'name',
      headerName: 'Form',
      flex: 1,
      minWidth: 160,
      renderCell: ({ row }) =>
        canConfigWrite ? (
          <Link to={editPath(row)} className="text-primary hover:underline">
            <span className="line-clamp-2" title={row.name}>
              {row.name}
            </span>
          </Link>
        ) : (
          <button type="button" className="text-left hover:underline" onClick={() => setViewing(row)}>
            {row.name}
          </button>
        ),
    },
    {
      field: 'form_version',
      headerName: 'Version',
      width: 90,
      sortable: false,
      renderCell: ({ row }) => <span className="text-sm">v{row.form_version}</span>,
    },
    {
      field: 'tag_ids',
      headerName: 'Tags',
      flex: 1,
      minWidth: 160,
      sortable: false,
      renderCell: ({ row }) => (
        <TagCell tags={(row.tag_ids ?? []).flatMap((id) => tagsById.get(id) ?? [])} />
      ),
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 120,
      renderCell: ({ row }) =>
        row.created_at ? (
          <span className="text-sm text-muted-foreground">{formatLocalDate(String(row.created_at))}</span>
        ) : (
          ''
        ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      hideable: false,
      resizable: false,
      renderCell: ({ row }) => (
        <RowActionsMenu
          label={row.name}
          actions={[
            { label: 'Properties', icon: Info, onSelect: () => setViewing(row) },
            canConfigWrite && { label: 'Edit', icon: Pencil, to: editPath(row) },
            canConfigWrite && {
              label: 'Rename',
              icon: PencilLine,
              onSelect: () => setNameEdit({ form: row, cloning: false }),
            },
            canConfigWrite && {
              label: 'Clone',
              icon: Copy,
              onSelect: () => setNameEdit({ form: row, cloning: true }),
            },
            { label: 'Download', icon: Download, onSelect: () => handleDownload(row) },
            canConfigWrite && {
              label: 'Delete',
              icon: Trash2,
              destructive: true,
              onSelect: () => setDeleting(row),
            },
          ]}
        />
      ),
    },
  ]

  return (
    <>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <SearchInput
            value={search}
            onChange={(value) => {
              setSearch(value)
              setPagination((p) => ({ ...p, page: 0 }))
            }}
            placeholder="Search forms"
          />
          <FilterBuilder
            fields={filterFields}
            value={filters}
            request={filterRequest}
            onChange={(items) => {
              setFilters(items)
              setPagination((p) => ({ ...p, page: 0 }))
            }}
          />
        </div>
        <ErrorAlert error={formsQuery.error} />
        <div className="h-150 min-h-[24rem]">
          <DataTable
            aria-label="Forms"
            rows={formsQuery.data?.forms ?? []}
            getRowId={(row) => row.form_revid}
            columns={withFilterFields(columns, filterFields)}
            activeFilterFields={activeFields(filters)}
            onFilterColumn={(field) => setFilterRequest({ field })}
            rowCount={formsQuery.data?.total_count ?? 0}
            loading={formsQuery.isFetching}
            paginationModel={pagination}
            onPaginationModelChange={setPagination}
            sortModel={sortModel}
            onSortModelChange={(model) => setSortModel(model.filter((s) => !NON_SORT_FIELDS.has(s.field)))}
            pageSizeOptions={[10, 25, 50]}
          />
        </div>
      </div>

      {viewing ? (
        <FormPropertiesPanel form={viewing} tagsById={tagsById} onClose={() => setViewing(null)} />
      ) : null}
      {nameEdit ? (
        <FormNameDialog
          organizationId={organizationId}
          originalName={nameEdit.cloning ? `${nameEdit.form.name} (Copy)` : nameEdit.form.name}
          isCloning={nameEdit.cloning}
          onClose={() => setNameEdit(null)}
          onSubmit={handleNameSubmit}
        />
      ) : null}
      <ConfirmDialog
        open={deleting !== null}
        title="Delete form"
        message={`Delete the form "${shortName(deleting?.name)}" and all its versions?`}
        busy={deleteBusy}
        error={deleteError}
        onConfirm={() => void confirmDelete()}
        onClose={() => {
          setDeleting(null)
          setDeleteError(null)
        }}
      />
    </>
  )
}

export default FormList
