'use client'

import {
  Copy,
  Download,
  Info,
  Pencil,
  PencilLine,
  Trash2,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import type { Prompt, Schema, Tag } from '@docrouter/sdk'

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
import { useInvalidateOrgLists, useOrgPrompts, useOrgSchemas, useOrgTags } from '@/api/orgQueries'
import { DocRouterAccountApi, DocRouterOrgApi } from '@/utils/api'
import { formatLocalDate } from '@/utils/date'
import { useOrgCapability } from '@/hooks/useOrgPermissions'
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities'

const DEFAULT_LLM_MODEL = 'gemini-2.0-flash'

const jsonStringifyForQuery = (value: unknown): string =>
  JSON.stringify(value, (_key, v) => (v instanceof Date ? v.toISOString() : v))

type PromptRow = Prompt & { created_by?: string }

function PromptNameDialog({
  initialName,
  isCloning,
  onClose,
  onSubmit,
}: {
  initialName: string
  isCloning: boolean
  onClose: () => void
  onSubmit: (name: string) => Promise<void>
}) {
  const [name, setName] = useState(initialName)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    setName(initialName)
  }, [initialName])

  const save = async () => {
    const trimmed = name.trim()
    if (!trimmed) return
    setBusy(true)
    setError(null)
    try {
      await onSubmit(trimmed)
      toast.success(isCloning ? 'Prompt cloned' : 'Prompt renamed')
      onClose()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <FormDialog
      title={isCloning ? 'Clone prompt' : 'Rename prompt'}
      submitLabel={isCloning ? 'Clone' : 'Save'}
      submitDisabled={!name.trim()}
      busy={busy}
      error={error}
      onSubmit={() => void save()}
      onClose={onClose}
    >
      <Field>
        <FieldLabel htmlFor="prompt-name">Name</FieldLabel>
        <Input id="prompt-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
      </Field>
    </FormDialog>
  )
}

function PromptPropertiesPanel({ prompt, onClose }: { prompt: PromptRow; onClose: () => void }) {
  const [createdByName, setCreatedByName] = useState<string | null>(null)
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])

  useEffect(() => {
    let cancelled = false
    if (!prompt.created_by) {
      setCreatedByName(null)
      return
    }
    void docRouterAccountApi
      .getUser(prompt.created_by)
      .then((user) => {
        if (!cancelled) setCreatedByName(user.name ?? prompt.created_by!)
      })
      .catch(() => {
        if (!cancelled) setCreatedByName(prompt.created_by!)
      })
    return () => {
      cancelled = true
    }
  }, [prompt.created_by, docRouterAccountApi])

  return (
    <PropertiesDialog
      title={prompt.name}
      description="Prompt properties"
      onClose={onClose}
      columns={2}
      properties={[
        { label: 'Name', value: prompt.name },
        { label: 'Version', value: `v${prompt.prompt_version}` },
        { label: 'Model', value: prompt.model || DEFAULT_LLM_MODEL },
        { label: 'Saved', value: prompt.created_at ? formatLocalDate(String(prompt.created_at)) : '—' },
        { label: 'Created by', value: prompt.created_by ? (createdByName ?? '…') : '—' },
        { label: 'Prompt ID', value: <span className="font-mono text-xs">{prompt.prompt_id}</span> },
        { label: 'Revision ID', value: <span className="font-mono text-xs">{prompt.prompt_revid}</span> },
        {
          label: 'Schema',
          value:
            prompt.schema_id && prompt.schema_version
              ? `${prompt.schema_id} v${prompt.schema_version}`
              : '—',
        },
      ]}
    />
  )
}

const PromptList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const { hasCapability: canConfigWrite } = useOrgCapability(organizationId, CAP_CONFIG_WRITE)
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])

  const [pagination, setPagination] = useState<PaginationModel>({ page: 0, pageSize: 25 })
  const [sortModel, setSortModel] = useState<SortModel>([{ field: 'name', sort: 'asc' }])
  const [filters, setFilters] = useState<FilterItem[]>([])
  const [filterRequest, setFilterRequest] = useState<{ field: string } | null>(null)
  const [search, setSearch] = useState('')
  const nameSearch = useDebounced(search.trim())
  const activeFilters = filters.filter(isActiveFilter)
  const sortForApi = sortModel.filter((s) => s.field !== 'actions')
  const promptsQuery = useOrgPrompts(organizationId, {
    skip: pagination.page * pagination.pageSize,
    limit: pagination.pageSize,
    nameSearch: nameSearch || undefined,
    sort: sortForApi.length ? jsonStringifyForQuery(sortForApi) : undefined,
    filters: activeFilters.length ? jsonStringifyForQuery({ items: activeFilters }) : undefined,
  })
  const tagsQuery = useOrgTags(organizationId, { skip: 0, limit: 100 })
  const schemasQuery = useOrgSchemas(organizationId, { skip: 0, limit: 100 })
  const invalidate = useInvalidateOrgLists(organizationId)
  const availableTags = tagsQuery.data?.tags ?? []
  const availableSchemas = schemasQuery.data?.schemas ?? []
  const tagsById = useMemo(() => new Map(availableTags.map((t) => [t.id, t])), [availableTags])
  const schemaNames = useMemo(
    () => new Map(availableSchemas.map((s) => [s.schema_id, s.name])),
    [availableSchemas],
  )

  const [viewing, setViewing] = useState<PromptRow | null>(null)
  const [nameEdit, setNameEdit] = useState<{ prompt: Prompt; cloning: boolean } | null>(null)
  const [deleting, setDeleting] = useState<Prompt | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState<unknown>(null)

  const editPath = (prompt: Prompt) => `/orgs/${organizationId}/prompts/${prompt.prompt_revid}`

  const handleRenameSubmit = async (newName: string) => {
    if (!nameEdit) return
    const { prompt, cloning } = nameEdit
    const promptConfig = {
      name: newName,
      content: prompt.content,
      schema_id: prompt.schema_id,
      schema_version: prompt.schema_version,
      tag_ids: prompt.tag_ids,
      model: prompt.model,
    }
    if (cloning) {
      await docRouterOrgApi.createPrompt({ prompt: promptConfig })
    } else {
      await docRouterOrgApi.updatePrompt({ promptId: prompt.prompt_id, prompt: promptConfig })
    }
    await invalidate.prompts()
  }

  const handleDownload = async (prompt: Prompt) => {
    try {
      let schema: Schema | undefined
      if (prompt.schema_id && prompt.schema_version) {
        const matchingSchema = availableSchemas.find((s) => s.schema_id === prompt.schema_id)
        if (matchingSchema) {
          schema = await docRouterOrgApi.getSchema({ schemaRevId: matchingSchema.schema_revid })
        }
      }
      const promptExport = {
        name: prompt.name,
        model: prompt.model || DEFAULT_LLM_MODEL,
        tags:
          prompt.tag_ids?.map((id) => tagsById.get(id)?.name ?? null).filter(Boolean) ?? [],
        content: prompt.content,
        schema: schema
          ? { name: schema.name, response_format: schema.response_format }
          : null,
      }
      const blob = new Blob([JSON.stringify(promptExport, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${prompt.name.replace(/\s+/g, '_')}_v${prompt.prompt_version}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('Download started')
    } catch {
      toast.error('Failed to download prompt')
    }
  }

  const confirmDelete = async () => {
    if (!deleting) return
    setDeleteBusy(true)
    setDeleteError(null)
    try {
      await docRouterOrgApi.deletePrompt({ promptId: deleting.prompt_id })
      toast.success('Prompt deleted')
      setDeleting(null)
      void invalidate.prompts()
    } catch (error) {
      setDeleteError(error)
    } finally {
      setDeleteBusy(false)
    }
  }

  const filterFields: FilterField[] = useMemo(
    () => [
      { field: 'name', label: 'Name', kind: 'text' as const },
      { field: 'content', label: 'Prompt text', kind: 'text' as const },
      { field: 'model', label: 'Model', kind: 'text' as const },
      { field: 'prompt_version', label: 'Version', kind: 'text' as const },
      {
        field: 'tag_ids',
        label: 'Tags',
        kind: 'tag' as const,
        single: true,
        options: availableTags.map((t) => ({ value: t.name, label: t.name })),
      },
      { field: 'created_at', label: 'Saved', kind: 'date' as const },
    ],
    [availableTags],
  )

  const columns: DataTableColumn<Prompt>[] = [
    {
      field: 'name',
      headerName: 'Prompt',
      flex: 1,
      minWidth: 180,
      renderCell: ({ row }) =>
        canConfigWrite ? (
          <Link to={editPath(row)} className="text-primary hover:underline" title={row.name}>
            {row.name}
          </Link>
        ) : (
          <button
            type="button"
            className="block min-w-0 max-w-full truncate text-left hover:underline"
            title={row.name}
            onClick={() => setViewing(row)}
          >
            {row.name}
          </button>
        ),
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
      field: 'schema_id',
      headerName: 'Schema',
      flex: 1,
      minWidth: 130,
      sortable: false,
      renderCell: ({ row }) => {
        if (!row.schema_id) return <span className="text-muted-foreground">—</span>
        const name = schemaNames.get(row.schema_id) ?? 'Schema'
        return (
          <span className="truncate text-sm" title={`${name} v${row.schema_version}`}>
            {name}:v{row.schema_version}
          </span>
        )
      },
    },
    {
      field: 'model',
      headerName: 'Model',
      flex: 1,
      minWidth: 120,
      renderCell: ({ row }) => (
        <span className="truncate text-sm text-muted-foreground">{row.model || DEFAULT_LLM_MODEL}</span>
      ),
    },
    {
      field: 'prompt_version',
      headerName: 'Version',
      width: 90,
      renderCell: ({ row }) => <span className="text-sm">v{row.prompt_version}</span>,
    },
    {
      field: 'created_at',
      headerName: 'Saved',
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
              onSelect: () => setNameEdit({ prompt: row, cloning: false }),
            },
            canConfigWrite && {
              label: 'Clone',
              icon: Copy,
              onSelect: () => setNameEdit({ prompt: row, cloning: true }),
            },
            { label: 'Download', icon: Download, onSelect: () => void handleDownload(row) },
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
            placeholder="Search prompts"
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
        <ErrorAlert error={promptsQuery.error} />
        <div className="h-150 min-h-[24rem]">
          <DataTable
            aria-label="Prompts"
            rows={promptsQuery.data?.prompts ?? []}
            getRowId={(row) => row.prompt_revid}
            columns={withFilterFields(columns, filterFields)}
            activeFilterFields={activeFields(filters)}
            onFilterColumn={(field) => setFilterRequest({ field })}
            rowCount={promptsQuery.data?.total_count ?? 0}
            loading={promptsQuery.isFetching}
            paginationModel={pagination}
            onPaginationModelChange={setPagination}
            sortModel={sortModel}
            onSortModelChange={setSortModel}
            pageSizeOptions={[10, 25, 50]}
          />
        </div>
      </div>

      {viewing ? <PromptPropertiesPanel prompt={viewing} onClose={() => setViewing(null)} /> : null}
      {nameEdit ? (
        <PromptNameDialog
          initialName={nameEdit.cloning ? `${nameEdit.prompt.name} (Copy)` : nameEdit.prompt.name}
          isCloning={nameEdit.cloning}
          onClose={() => setNameEdit(null)}
          onSubmit={handleRenameSubmit}
        />
      ) : null}
      <ConfirmDialog
        open={deleting !== null}
        title="Delete prompt"
        message={`Delete the prompt "${shortName(deleting?.name)}" and all its versions?`}
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

export default PromptList
