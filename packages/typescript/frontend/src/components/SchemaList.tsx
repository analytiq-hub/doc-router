'use client'

import { Copy, Download, Info, Pencil, PencilLine, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import type { Schema, SchemaProperty, SchemaResponseFormat } from '@docrouter/sdk'
import { SchemaField } from '@/types/ui'

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
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { useDebounced } from '@/lib/useDebounced'
import { shortName } from '@/lib/shortName'
import { DocRouterAccountApi, DocRouterOrgApi } from '@/utils/api'
import { formatLocalDate } from '@/utils/date'
import { useOrgCapability } from '@/hooks/useOrgPermissions'
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities'

const jsonStringifyForQuery = (value: unknown): string =>
  JSON.stringify(value, (_key, v) => (v instanceof Date ? v.toISOString() : v))

function jsonSchemaToFields(responseFormat: SchemaResponseFormat): SchemaField[] {
  const fields: SchemaField[] = []
  const properties = responseFormat.json_schema.schema.properties

  const processProperty = (name: string, prop: SchemaProperty): SchemaField => {
    let fieldType: SchemaField['type']
    switch (prop.type) {
      case 'string':
        fieldType = 'str'
        break
      case 'integer':
        fieldType = 'int'
        break
      case 'number':
        fieldType = 'float'
        break
      case 'boolean':
        fieldType = 'bool'
        break
      case 'array':
        fieldType = 'array'
        break
      case 'object':
        fieldType = 'object'
        break
      default:
        fieldType = 'str'
    }
    return { name, type: fieldType, description: prop.description }
  }

  Object.entries(properties).forEach(([name, prop]) => {
    fields.push(processProperty(name, prop))
  })
  return fields
}

type SchemaRow = Schema & { created_by?: string }

function SchemaNameDialog({
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
  const [error, setError] = useState<string | null>(null)
  const [existingNames, setExistingNames] = useState<string[]>([])

  useEffect(() => {
    setName(originalName)
  }, [originalName])

  useEffect(() => {
    void docRouterOrgApi.listSchemas({ limit: 100 }).then((res) => {
      setExistingNames(res.schemas.map((s) => s.name.toLowerCase()))
    })
  }, [docRouterOrgApi])

  const save = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Schema name cannot be empty')
      return
    }
    if (
      trimmed.toLowerCase() !== originalName.toLowerCase() &&
      existingNames.includes(trimmed.toLowerCase())
    ) {
      setError('A schema with this name already exists')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await onSubmit(trimmed)
      toast.success(isCloning ? 'Schema cloned' : 'Schema renamed')
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <FormDialog
      title={isCloning ? 'Clone schema' : 'Rename schema'}
      submitLabel={isCloning ? 'Clone' : 'Save'}
      submitDisabled={!name.trim() || (!isCloning && name.trim() === originalName)}
      busy={busy}
      error={error}
      onSubmit={() => void save()}
      onClose={onClose}
    >
      <Field>
        <FieldLabel htmlFor="schema-name">Name</FieldLabel>
        <Input id="schema-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
      </Field>
    </FormDialog>
  )
}

function SchemaPropertiesPanel({ schema, onClose }: { schema: SchemaRow; onClose: () => void }) {
  const [createdByName, setCreatedByName] = useState<string | null>(null)
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), [])
  const fieldCount = jsonSchemaToFields(schema.response_format).length

  useEffect(() => {
    let cancelled = false
    if (!schema.created_by) {
      setCreatedByName(null)
      return
    }
    void docRouterAccountApi
      .getUser(schema.created_by)
      .then((user) => {
        if (!cancelled) setCreatedByName(user.name ?? schema.created_by!)
      })
      .catch(() => {
        if (!cancelled) setCreatedByName(schema.created_by!)
      })
    return () => {
      cancelled = true
    }
  }, [schema.created_by, docRouterAccountApi])

  return (
    <PropertiesDialog
      title={schema.name}
      description="Schema properties"
      onClose={onClose}
      columns={2}
      properties={[
        { label: 'Name', value: schema.name },
        { label: 'Version', value: `v${schema.schema_version}` },
        { label: 'Fields', value: fieldCount },
        { label: 'Created', value: schema.created_at ? formatLocalDate(String(schema.created_at)) : '—' },
        { label: 'Created by', value: schema.created_by ? (createdByName ?? '…') : '—' },
        { label: 'Schema ID', value: <span className="font-mono text-xs">{schema.schema_id}</span> },
        { label: 'Revision ID', value: <span className="font-mono text-xs">{schema.schema_revid}</span> },
      ]}
    />
  )
}

const SchemaList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const { hasCapability: canConfigWrite } = useOrgCapability(organizationId, CAP_CONFIG_WRITE)
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])

  const [schemas, setSchemas] = useState<Schema[]>([])
  const [loadError, setLoadError] = useState<unknown>(null)
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [pagination, setPagination] = useState<PaginationModel>({ page: 0, pageSize: 25 })
  const [sortModel, setSortModel] = useState<SortModel>([{ field: 'created_at', sort: 'desc' }])
  const [filters, setFilters] = useState<FilterItem[]>([])
  const [filterRequest, setFilterRequest] = useState<{ field: string } | null>(null)
  const [search, setSearch] = useState('')
  const nameSearch = useDebounced(search.trim())
  const activeFilters = filters.filter(isActiveFilter)

  const [viewing, setViewing] = useState<SchemaRow | null>(null)
  const [nameEdit, setNameEdit] = useState<{ schema: Schema; cloning: boolean } | null>(null)
  const [deleting, setDeleting] = useState<Schema | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState<unknown>(null)

  const loadSchemas = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const sortForApi = sortModel.filter((s) => s.field !== 'fields' && s.field !== 'actions')
      const response = await docRouterOrgApi.listSchemas({
        skip: pagination.page * pagination.pageSize,
        limit: pagination.pageSize,
        nameSearch: nameSearch || undefined,
        sort: sortForApi.length ? jsonStringifyForQuery(sortForApi) : undefined,
        filters: activeFilters.length ? jsonStringifyForQuery({ items: activeFilters }) : undefined,
      })
      setSchemas(response.schemas)
      setTotal(response.total_count ?? response.schemas.length)
    } catch (error) {
      setLoadError(error)
    } finally {
      setLoading(false)
    }
  }, [docRouterOrgApi, pagination, nameSearch, sortModel, activeFilters])

  useEffect(() => {
    void loadSchemas()
  }, [loadSchemas])

  const editPath = (schema: Schema) => `/orgs/${organizationId}/schemas/${schema.schema_revid}`

  const handleNameSubmit = async (newName: string) => {
    if (!nameEdit) return
    const { schema, cloning } = nameEdit
    const schemaConfig = { name: newName, response_format: schema.response_format }
    if (cloning) {
      await docRouterOrgApi.createSchema(schemaConfig)
    } else {
      await docRouterOrgApi.updateSchema({ schemaId: schema.schema_id, schema: schemaConfig })
    }
    await loadSchemas()
  }

  const handleDownload = (schema: Schema) => {
    try {
      const schemaJson = JSON.stringify(schema.response_format.json_schema, null, 2)
      const blob = new Blob([schemaJson], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${schema.name.replace(/\s+/g, '_')}_schema.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('Download started')
    } catch {
      toast.error('Failed to download schema')
    }
  }

  const confirmDelete = async () => {
    if (!deleting) return
    setDeleteBusy(true)
    setDeleteError(null)
    try {
      await docRouterOrgApi.deleteSchema({ schemaId: deleting.schema_id })
      toast.success('Schema deleted')
      setDeleting(null)
      void loadSchemas()
    } catch (error) {
      setDeleteError(error)
    } finally {
      setDeleteBusy(false)
    }
  }

  const filterFields: FilterField[] = [
    { field: 'name', label: 'Name', kind: 'text' },
    { field: 'schema_version', label: 'Version', kind: 'text' },
    { field: 'created_at', label: 'Created', kind: 'date' },
  ]

  const columns: DataTableColumn<Schema>[] = [
    {
      field: 'name',
      headerName: 'Schema',
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
      field: 'fields',
      headerName: 'Fields',
      flex: 2,
      minWidth: 200,
      sortable: false,
      hideable: false,
      renderCell: ({ row }) => {
        const fields = jsonSchemaToFields(row.response_format)
        return (
          <ul className="flex flex-col gap-0.5 text-sm text-muted-foreground">
            {fields.map((field) => (
              <li key={field.name} className="truncate" title={`${field.name}: ${field.type}`}>
                {`${field.name}: ${field.type}`}
              </li>
            ))}
          </ul>
        )
      },
    },
    {
      field: 'schema_version',
      headerName: 'Version',
      width: 90,
      sortable: false,
      renderCell: ({ row }) => <span className="text-sm">v{row.schema_version}</span>,
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
              onSelect: () => setNameEdit({ schema: row, cloning: false }),
            },
            canConfigWrite && {
              label: 'Clone',
              icon: Copy,
              onSelect: () => setNameEdit({ schema: row, cloning: true }),
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
            placeholder="Search schemas"
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
        <ErrorAlert error={loadError} />
        <div className="h-150 min-h-[24rem]">
          <DataTable
            aria-label="Schemas"
            rows={schemas}
            getRowId={(row) => row.schema_revid}
            columns={withFilterFields(columns, filterFields)}
            activeFilterFields={activeFields(filters)}
            onFilterColumn={(field) => setFilterRequest({ field })}
            rowCount={total}
            loading={loading}
            paginationModel={pagination}
            onPaginationModelChange={setPagination}
            sortModel={sortModel}
            onSortModelChange={(model) =>
              setSortModel(model.filter((s) => s.field !== 'fields' && s.field !== 'actions'))
            }
            pageSizeOptions={[10, 25, 50]}
            autoRowHeight
          />
        </div>
      </div>

      {viewing ? <SchemaPropertiesPanel schema={viewing} onClose={() => setViewing(null)} /> : null}
      {nameEdit ? (
        <SchemaNameDialog
          organizationId={organizationId}
          originalName={nameEdit.cloning ? `${nameEdit.schema.name} (Copy)` : nameEdit.schema.name}
          isCloning={nameEdit.cloning}
          onClose={() => setNameEdit(null)}
          onSubmit={handleNameSubmit}
        />
      ) : null}
      <ConfirmDialog
        open={deleting !== null}
        title="Delete schema"
        message={`Delete the schema "${shortName(deleting?.name)}" and all its versions?`}
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

export default SchemaList
