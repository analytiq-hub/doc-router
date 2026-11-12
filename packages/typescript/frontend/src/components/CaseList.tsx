'use client'

import { FolderOpen, Info, Pencil, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Case } from '@docrouter/sdk'

import { useInvalidateOrgLists, useOrgAllTags, useOrgCases } from '@/api/orgQueries'
import CaseDeleteDialog from '@/components/CaseDeleteDialog'
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
import { PropertiesDialog } from '@/components/PropertiesDialog'
import { RowActionsMenu } from '@/components/RowActionsMenu'
import { SearchInput } from '@/components/SearchInput'
import { TagCell } from '@/components/TagCell'
import { Input } from '@/components/ui/input'
import { useDebounced } from '@/lib/useDebounced'
import { useOrgCapability } from '@/hooks/useOrgPermissions'
import { CAP_DOCUMENTS_WRITE } from '@/utils/orgCapabilities'
import { caseDisplayName } from '@/utils/caseDisplayName'
import { formatLocalDate } from '@/utils/date'
import { parseAndEncodeMetadataSearch } from '@/utils/documentListQuery'
import { useRouter } from '@/utils/appRouter'

const jsonStringifyForQuery = (value: unknown): string =>
  JSON.stringify(value, (_key, v) => (v instanceof Date ? v.toISOString() : v))

const NON_SORT_FIELDS = new Set(['tag_ids', 'document_count', 'actions'])

const caseDetailHref = (organizationId: string, caseId: string) =>
  `/orgs/${organizationId}/cases/${encodeURIComponent(caseId)}`

const CaseList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter()
  const { hasCapability: canWriteDocuments } = useOrgCapability(organizationId, CAP_DOCUMENTS_WRITE)
  const invalidate = useInvalidateOrgLists(organizationId)

  const [pagination, setPagination] = useState<PaginationModel>({ page: 0, pageSize: 25 })
  const [sortModel, setSortModel] = useState<SortModel>([{ field: 'updated_at', sort: 'desc' }])
  const [filters, setFilters] = useState<FilterItem[]>([])
  const [filterRequest, setFilterRequest] = useState<{ field: string } | null>(null)
  const [search, setSearch] = useState('')
  const caseIdSearch = useDebounced(search.trim())
  const [metadataSearch, setMetadataSearch] = useState('')
  const metadataSearchDebounced = useDebounced(metadataSearch.trim())

  const activeFilters = filters.filter(isActiveFilter)
  const sortForApi = sortModel.filter((s) => !NON_SORT_FIELDS.has(s.field))
  const metadataForApi = metadataSearchDebounced
    ? parseAndEncodeMetadataSearch(metadataSearchDebounced) || undefined
    : undefined

  const casesQuery = useOrgCases(organizationId, {
    skip: pagination.page * pagination.pageSize,
    limit: pagination.pageSize,
    caseIdSearch: caseIdSearch || undefined,
    metadataSearch: metadataForApi,
    sort: sortForApi.length ? jsonStringifyForQuery(sortForApi) : undefined,
    filters: activeFilters.length ? jsonStringifyForQuery({ items: activeFilters }) : undefined,
  })
  const tagsQuery = useOrgAllTags(organizationId)
  const tagsById = useMemo(
    () => new Map((tagsQuery.data ?? []).map((tag) => [tag.id, tag])),
    [tagsQuery.data],
  )

  const [viewing, setViewing] = useState<Case | null>(null)
  const [deleting, setDeleting] = useState<Case | null>(null)

  const filterFields: FilterField[] = useMemo(
    () => [
      { field: 'name', label: 'Name', kind: 'text' as const },
      { field: 'case_id', label: 'Case ID', kind: 'text' as const },
      {
        field: 'tag_ids',
        label: 'Tags',
        kind: 'tag' as const,
        single: true,
        options: (tagsQuery.data ?? []).map((t) => ({ value: t.name, label: t.name })),
      },
      { field: 'created_at', label: 'Created', kind: 'date' as const },
      { field: 'updated_at', label: 'Updated', kind: 'date' as const },
    ],
    [tagsQuery.data],
  )

  const columns: DataTableColumn<Case>[] = [
    {
      field: 'name',
      headerName: 'Case name',
      flex: 1,
      minWidth: 180,
      valueGetter: (_value, row) => caseDisplayName(row),
      renderCell: ({ row }) => {
        const name = caseDisplayName(row)
        return (
          <Link
            to={caseDetailHref(organizationId, row.case_id)}
            className="text-primary hover:underline"
            title={name}
          >
            <span className="line-clamp-2">{name}</span>
          </Link>
        )
      },
    },
    {
      field: 'case_id',
      headerName: 'Case ID',
      flex: 1,
      minWidth: 140,
      renderCell: ({ row }) => (
        <span className="truncate font-mono text-xs text-muted-foreground" title={row.case_id}>
          {row.case_id}
        </span>
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
      field: 'document_count',
      headerName: 'Documents',
      width: 110,
      sortable: false,
      renderCell: ({ row }) => <span className="text-sm tabular-nums">{row.document_count ?? 0}</span>,
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
      field: 'updated_at',
      headerName: 'Updated',
      width: 120,
      renderCell: ({ row }) =>
        row.updated_at ? (
          <span className="text-sm text-muted-foreground">{formatLocalDate(String(row.updated_at))}</span>
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
          label={caseDisplayName(row)}
          actions={[
            { label: 'Properties', icon: Info, onSelect: () => setViewing(row) },
            { label: 'Open', icon: FolderOpen, to: caseDetailHref(organizationId, row.case_id) },
            canWriteDocuments && {
              label: 'Edit',
              icon: Pencil,
              onSelect: () =>
                router.push(`/orgs/${organizationId}/cases/${encodeURIComponent(row.case_id)}/edit`),
            },
            canWriteDocuments && {
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
            placeholder="Search cases (ID or name)"
          />
          <Input
            className="h-9 w-64 max-w-full shrink-0"
            placeholder="Metadata (key=value,...)"
            aria-label="Search case metadata"
            value={metadataSearch}
            onChange={(e) => {
              setMetadataSearch(e.target.value)
              setPagination((p) => ({ ...p, page: 0 }))
            }}
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
        <ErrorAlert error={casesQuery.error} />
        <div className="h-150 min-h-[24rem]">
          <DataTable
            aria-label="Cases"
            rows={casesQuery.data?.cases ?? []}
            getRowId={(row) => row.case_id}
            columns={withFilterFields(columns, filterFields)}
            activeFilterFields={activeFields(filters)}
            onFilterColumn={(field) => setFilterRequest({ field })}
            rowCount={casesQuery.data?.total_count ?? 0}
            loading={casesQuery.isFetching}
            paginationModel={pagination}
            onPaginationModelChange={setPagination}
            sortModel={sortModel}
            onSortModelChange={(model) =>
              setSortModel(model.filter((s) => !NON_SORT_FIELDS.has(s.field)))
            }
            pageSizeOptions={[10, 25, 50]}
          />
        </div>
      </div>

      {viewing ? (
        <PropertiesDialog
          title={caseDisplayName(viewing)}
          description="Case properties"
          onClose={() => setViewing(null)}
          properties={[
            { label: 'Name', value: viewing.name?.trim() || '—' },
            { label: 'Case ID', value: <span className="font-mono text-xs">{viewing.case_id}</span> },
            { label: 'Documents', value: String(viewing.document_count ?? 0) },
            {
              label: 'Created',
              value: viewing.created_at ? formatLocalDate(String(viewing.created_at)) : '—',
            },
            {
              label: 'Updated',
              value: viewing.updated_at ? formatLocalDate(String(viewing.updated_at)) : '—',
            },
          ]}
        />
      ) : null}

      <CaseDeleteDialog
        open={deleting !== null}
        organizationId={organizationId}
        caseRow={deleting}
        canCascadeDelete={canWriteDocuments}
        onClose={() => setDeleting(null)}
        onDeleted={() => void invalidate.cases()}
      />
    </>
  )
}

export default CaseList
