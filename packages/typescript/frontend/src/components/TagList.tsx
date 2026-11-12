'use client'

import { Info, Pencil, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import type { Tag } from '@docrouter/sdk'

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
import { DEFAULT_TAG_COLOR, TagBadge } from '@/components/TagBadge'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useDebounced } from '@/lib/useDebounced'
import { shortName } from '@/lib/shortName'
import { useInvalidateOrgLists, useOrgTags } from '@/api/orgQueries'
import { DocRouterAccountApi, DocRouterOrgApi } from '@/utils/api'
import { formatLocalDate } from '@/utils/date'
import { useOrgCapability } from '@/hooks/useOrgPermissions'
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities'
import { designTokens } from '@/lib/designTokens'

const jsonStringifyForQuery = (value: unknown): string =>
  JSON.stringify(value, (_key, v) => (v instanceof Date ? v.toISOString() : v))

type TagWithCreator = Tag & { created_by?: string }

function TagSaveDialog({
  organizationId,
  tag,
  onClose,
  onSaved,
}: {
  organizationId: string
  tag: Tag | 'new'
  onClose: () => void
  onSaved: () => void
}) {
  const existing = tag === 'new' ? null : tag
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])
  const [name, setName] = useState(existing?.name ?? '')
  const [color, setColor] = useState(existing?.color ?? designTokens.brand ?? DEFAULT_TAG_COLOR)
  const [description, setDescription] = useState(existing?.description ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const save = async () => {
    const trimmedName = name.trim()
    if (!trimmedName) return
    setBusy(true)
    setError(null)
    try {
      const payload = {
        name: trimmedName,
        color,
        description: description.trim() || undefined,
      }
      if (existing?.id) {
        await docRouterOrgApi.updateTag({ tagId: existing.id, tag: payload })
        toast.success('Tag saved')
      } else {
        await docRouterOrgApi.createTag({ tag: payload })
        toast.success('Tag created')
      }
      onSaved()
      onClose()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <FormDialog
      title={existing ? 'Edit tag' : 'New tag'}
      submitLabel="Save"
      submitDisabled={!name.trim()}
      busy={busy}
      error={error}
      onSubmit={() => void save()}
      onClose={onClose}
    >
      <Field>
        <FieldLabel htmlFor="tag-name">Name</FieldLabel>
        <Input id="tag-name" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
      </Field>
      <Field>
        <FieldLabel htmlFor="tag-color">Color</FieldLabel>
        <div>
          <Input
            id="tag-color"
            type="color"
            value={color}
            onChange={(e) => setColor(e.target.value)}
            className="h-9 w-20 p-1"
          />
        </div>
      </Field>
      <Field>
        <FieldLabel htmlFor="tag-description">Description</FieldLabel>
        <Textarea id="tag-description" value={description} onChange={(e) => setDescription(e.target.value)} />
      </Field>
    </FormDialog>
  )
}

function TagPropertiesPanel({ tag, onClose }: { tag: TagWithCreator; onClose: () => void }) {
  const [createdByName, setCreatedByName] = useState<string | null>(null)
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])

  useEffect(() => {
    let cancelled = false
    const createdBy = tag.created_by
    if (!createdBy) {
      setCreatedByName(null)
      return
    }
    void docRouterAccountApi
      .getUser(createdBy)
      .then((user) => {
        if (!cancelled) setCreatedByName(user.name ?? createdBy)
      })
      .catch(() => {
        if (!cancelled) setCreatedByName(createdBy)
      })
    return () => {
      cancelled = true
    }
  }, [tag.created_by, docRouterAccountApi])

  return (
    <PropertiesDialog
      title={tag.name}
      description="Tag properties"
      onClose={onClose}
      properties={[
        { label: 'Name', value: tag.name },
        { label: 'Color', value: tag.color ?? `${DEFAULT_TAG_COLOR} (default)` },
        { label: 'Description', value: tag.description },
        {
          label: 'Created',
          value: tag.created_at ? formatLocalDate(String(tag.created_at)) : '—',
        },
        {
          label: 'Created by',
          value: tag.created_by ? (createdByName ?? 'Loading…') : '—',
        },
        { label: 'ID', value: <span className="font-mono text-xs">{tag.id}</span> },
      ]}
    />
  )
}

export interface TagListProps {
  organizationId: string
  /** Wire the page header “New tag” button to open the create dialog. */
  registerNewTag?: (open: () => void) => void
}

const TagList: React.FC<TagListProps> = ({ organizationId, registerNewTag }) => {
  const { hasCapability: canConfigWrite } = useOrgCapability(organizationId, CAP_CONFIG_WRITE)
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])

  const [pagination, setPagination] = useState<PaginationModel>({ page: 0, pageSize: 25 })
  const [sortModel, setSortModel] = useState<SortModel>([{ field: 'created_at', sort: 'desc' }])
  const [filters, setFilters] = useState<FilterItem[]>([])
  const [filterRequest, setFilterRequest] = useState<{ field: string } | null>(null)
  const [search, setSearch] = useState('')
  const nameSearch = useDebounced(search.trim())
  const [editing, setEditing] = useState<Tag | 'new' | null>(null)
  const [viewing, setViewing] = useState<TagWithCreator | null>(null)
  const [deleting, setDeleting] = useState<Tag | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState<unknown>(null)

  const activeFilters = filters.filter(isActiveFilter)
  const sortForApi = sortModel.filter((s) => s.field !== 'actions')
  const tagsQuery = useOrgTags(organizationId, {
    skip: pagination.page * pagination.pageSize,
    limit: pagination.pageSize,
    nameSearch: nameSearch || undefined,
    sort: sortForApi.length ? jsonStringifyForQuery(sortForApi) : undefined,
    filters: activeFilters.length ? jsonStringifyForQuery({ items: activeFilters }) : undefined,
  })
  const invalidate = useInvalidateOrgLists(organizationId)

  const filterFields: FilterField[] = [
    { field: 'name', label: 'Name', kind: 'text' },
    { field: 'description', label: 'Description', kind: 'text' },
    { field: 'created_at', label: 'Created', kind: 'date' },
  ]

  useEffect(() => {
    registerNewTag?.(() => setEditing('new'))
  }, [registerNewTag])

  const columns: DataTableColumn<Tag>[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      minWidth: 160,
      renderCell: ({ row }) => (
        <button
          type="button"
          className={`inline-flex max-w-full items-center text-left ${canConfigWrite ? 'cursor-pointer' : 'cursor-default'}`}
          onClick={() => (canConfigWrite ? setEditing(row) : setViewing(row))}
        >
          <TagBadge tag={row} />
        </button>
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      minWidth: 200,
      renderCell: ({ row }) => (
        <span className="line-clamp-2 text-sm" title={row.description ?? ''}>
          {row.description ?? ''}
        </span>
      ),
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 190,
      valueGetter: (_value, row) => (row.created_at ? new Date(String(row.created_at)) : null),
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
            canConfigWrite && { label: 'Edit', icon: Pencil, onSelect: () => setEditing(row) },
            canConfigWrite && { label: 'Delete', icon: Trash2, destructive: true, onSelect: () => setDeleting(row) },
          ]}
        />
      ),
    },
  ]

  const confirmDelete = async () => {
    if (!deleting) return
    setDeleteBusy(true)
    setDeleteError(null)
    try {
      await docRouterOrgApi.deleteTag({ tagId: deleting.id })
      toast.success('Tag deleted')
      setDeleting(null)
      void invalidate.tags()
    } catch (error) {
      setDeleteError(error)
    } finally {
      setDeleteBusy(false)
    }
  }

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
            placeholder="Search tags"
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
        <ErrorAlert error={tagsQuery.error} />
        <div className="h-150 min-h-[24rem]">
          <DataTable
            aria-label="Tags"
            rows={tagsQuery.data?.tags ?? []}
            columns={withFilterFields(columns, filterFields)}
            activeFilterFields={activeFields(filters)}
            onFilterColumn={(field) => setFilterRequest({ field })}
            rowCount={tagsQuery.data?.total_count ?? 0}
            loading={tagsQuery.isFetching}
            paginationModel={pagination}
            onPaginationModelChange={setPagination}
            sortModel={sortModel}
            onSortModelChange={setSortModel}
            pageSizeOptions={[10, 25, 50]}
          />
        </div>
      </div>

      {viewing ? <TagPropertiesPanel tag={viewing} onClose={() => setViewing(null)} /> : null}
      {editing ? (
        <TagSaveDialog
          organizationId={organizationId}
          tag={editing}
          onClose={() => setEditing(null)}
          onSaved={() => void invalidate.tags()}
        />
      ) : null}
      <ConfirmDialog
        open={deleting !== null}
        title="Delete tag"
        message={`Delete the tag "${shortName(deleting?.name)}"?`}
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

export default TagList
