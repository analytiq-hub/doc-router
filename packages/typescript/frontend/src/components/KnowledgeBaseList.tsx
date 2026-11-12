'use client'

import { FolderOpen, Info, Pencil, RefreshCw, Search, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import type { KnowledgeBase, KBStatus } from '@docrouter/sdk'

import { useInvalidateOrgLists, useOrgKnowledgeBases, useOrgTags } from '@/api/orgQueries'
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
import KnowledgeBaseInfoModal from '@/components/KnowledgeBaseInfoModal'
import { RowActionsMenu } from '@/components/RowActionsMenu'
import { SearchInput } from '@/components/SearchInput'
import { TagCell } from '@/components/TagCell'
import { Badge } from '@/components/ui/badge'
import { DocRouterOrgApi } from '@/utils/api'
import { formatLocalDate } from '@/utils/date'
import { useOrgCapability } from '@/hooks/useOrgPermissions'
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities'
import { useRouter } from '@/utils/appRouter'
import { shortName } from '@/lib/shortName'

const jsonStringifyForQuery = (value: unknown): string =>
  JSON.stringify(value, (_key, v) => (v instanceof Date ? v.toISOString() : v))

const NON_SORT_FIELDS = new Set(['document_count', 'chunk_count', 'tag_ids', 'actions'])

const KB_POLL_MS_INDEXING = 5_000
const KB_POLL_MS_SLOW = 30_000

function statusVariant(status: KBStatus): 'success' | 'warning' | 'danger' | 'outline' {
  switch (status) {
    case 'active':
      return 'success'
    case 'indexing':
      return 'warning'
    case 'error':
      return 'danger'
    default:
      return 'outline'
  }
}

const KnowledgeBaseList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter()
  const { hasCapability: canConfigWrite } = useOrgCapability(organizationId, CAP_CONFIG_WRITE)
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])
  const invalidate = useInvalidateOrgLists(organizationId)

  const [pagination, setPagination] = useState<PaginationModel>({ page: 0, pageSize: 25 })
  const [sortModel, setSortModel] = useState<SortModel>([{ field: 'created_at', sort: 'desc' }])
  const [filters, setFilters] = useState<FilterItem[]>([])
  const [filterRequest, setFilterRequest] = useState<{ field: string } | null>(null)
  const [search, setSearch] = useState('')
  const nameSearch = search.trim()

  const activeFilters = filters.filter(isActiveFilter)
  const sortForApi = sortModel.filter((s) => !NON_SORT_FIELDS.has(s.field))
  const listParams = {
    skip: pagination.page * pagination.pageSize,
    limit: pagination.pageSize,
    name_search: nameSearch || undefined,
    sort: sortForApi.length ? jsonStringifyForQuery(sortForApi) : undefined,
    filters: activeFilters.length ? jsonStringifyForQuery({ items: activeFilters }) : undefined,
  }

  const kbQuery = useOrgKnowledgeBases(organizationId, listParams, {
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const kbs = query.state.data?.knowledge_bases ?? []
      if (!kbs.length || kbs.every((kb) => kb.status === 'active')) return false
      return kbs.some((kb) => kb.status === 'indexing') ? KB_POLL_MS_INDEXING : KB_POLL_MS_SLOW
    },
  })

  const tagsQuery = useOrgTags(organizationId, { skip: 0, limit: 200 })
  const tagsById = useMemo(
    () => new Map((tagsQuery.data?.tags ?? []).map((tag) => [tag.id, tag])),
    [tagsQuery.data?.tags],
  )

  const [infoKb, setInfoKb] = useState<KnowledgeBase | null>(null)
  const [deleting, setDeleting] = useState<KnowledgeBase | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState<unknown>(null)

  const tabUrl = (tab: string, kbId: string) =>
    `/orgs/${organizationId}/knowledge-bases?tab=${tab}&kbId=${encodeURIComponent(kbId)}`

  const handleReconcile = async (kb: KnowledgeBase) => {
    try {
      const result = await docRouterOrgApi.reconcileKnowledgeBase({ kbId: kb.kb_id, dry_run: false })
      toast.success(
        `Reconciliation: ${result.missing_documents.length} missing, ${result.stale_documents.length} stale, ${result.orphaned_vectors} orphaned vectors`,
      )
      void invalidate.knowledgeBases()
    } catch (error) {
      toast.error('Reconciliation failed')
      console.error(error)
    }
  }

  const confirmDelete = async () => {
    if (!deleting) return
    setDeleteBusy(true)
    setDeleteError(null)
    try {
      await docRouterOrgApi.deleteKnowledgeBase({ kbId: deleting.kb_id })
      toast.success('Knowledge base deleted')
      setDeleting(null)
      void invalidate.knowledgeBases()
    } catch (error) {
      setDeleteError(error)
    } finally {
      setDeleteBusy(false)
    }
  }

  const filterFields: FilterField[] = useMemo(
    () => [
      { field: 'name', label: 'Name', kind: 'text' as const },
      { field: 'description', label: 'Description', kind: 'text' as const },
      {
        field: 'status',
        label: 'Status',
        kind: 'select' as const,
        options: [
          { value: 'active', label: 'active' },
          { value: 'indexing', label: 'indexing' },
          { value: 'error', label: 'error' },
        ],
      },
      { field: 'embedding_model', label: 'Model', kind: 'text' as const },
      {
        field: 'tag_ids',
        label: 'Tags',
        kind: 'tag' as const,
        single: true,
        options: (tagsQuery.data?.tags ?? []).map((t) => ({ value: t.name, label: t.name })),
      },
      { field: 'created_at', label: 'Created', kind: 'date' as const },
      { field: 'updated_at', label: 'Updated', kind: 'date' as const },
    ],
    [tagsQuery.data?.tags],
  )

  const columns: DataTableColumn<KnowledgeBase>[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      minWidth: 160,
      renderCell: ({ row }) => (
        <Link
          to={canConfigWrite ? tabUrl('edit', row.kb_id) : tabUrl('search', row.kb_id)}
          className="text-primary hover:underline"
        >
          <span className="line-clamp-2 font-medium" title={row.name}>
            {row.name}
          </span>
        </Link>
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1.5,
      minWidth: 180,
      sortable: false,
      renderCell: ({ row }) => (
        <span className="line-clamp-2 text-sm text-muted-foreground" title={row.description ?? ''}>
          {row.description?.trim() || '—'}
        </span>
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 110,
      renderCell: ({ row }) => (
        <Badge variant={statusVariant(row.status)} className="capitalize">
          {row.status}
        </Badge>
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
      field: 'chunk_count',
      headerName: 'Chunks',
      width: 100,
      sortable: false,
      renderCell: ({ row }) => (
        <span className="text-sm tabular-nums">{(row.chunk_count ?? 0).toLocaleString()}</span>
      ),
    },
    {
      field: 'embedding_model',
      headerName: 'Model',
      flex: 1,
      minWidth: 140,
      renderCell: ({ row }) => (
        <span className="truncate text-sm text-muted-foreground" title={row.embedding_model}>
          {row.embedding_model}
        </span>
      ),
    },
    {
      field: 'tag_ids',
      headerName: 'Tags',
      flex: 1,
      minWidth: 140,
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
            canConfigWrite && {
              label: 'Edit',
              icon: Pencil,
              onSelect: () => router.push(tabUrl('edit', row.kb_id)),
            },
            { label: 'View documents', icon: FolderOpen, onSelect: () => router.push(tabUrl('documents', row.kb_id)) },
            { label: 'Search', icon: Search, onSelect: () => router.push(tabUrl('search', row.kb_id)) },
            { label: 'Properties', icon: Info, onSelect: () => setInfoKb(row) },
            { label: 'Reconcile', icon: RefreshCw, onSelect: () => void handleReconcile(row) },
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
            placeholder="Search knowledge bases"
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
        <ErrorAlert error={kbQuery.error} />
        <div className="h-150 min-h-[24rem]">
          <DataTable
            aria-label="Knowledge bases"
            rows={kbQuery.data?.knowledge_bases ?? []}
            getRowId={(row) => row.kb_id}
            columns={withFilterFields(columns, filterFields)}
            activeFilterFields={activeFields(filters)}
            onFilterColumn={(field) => setFilterRequest({ field })}
            rowCount={kbQuery.data?.total_count ?? 0}
            loading={kbQuery.isFetching}
            paginationModel={pagination}
            onPaginationModelChange={setPagination}
            sortModel={sortModel}
            onSortModelChange={(model) =>
              setSortModel(model.filter((s) => !NON_SORT_FIELDS.has(s.field)))
            }
            pageSizeOptions={[10, 25, 50]}
            autoRowHeight
          />
        </div>
      </div>

      {infoKb ? (
        <KnowledgeBaseInfoModal
          isOpen
          onClose={() => setInfoKb(null)}
          kb={infoKb}
          organizationId={organizationId}
          onReconcile={async () => {
            void invalidate.knowledgeBases()
            try {
              const updated = await docRouterOrgApi.getKnowledgeBase({ kbId: infoKb.kb_id })
              setInfoKb(updated)
            } catch {
              void invalidate.knowledgeBases()
            }
          }}
        />
      ) : null}

      <ConfirmDialog
        open={deleting !== null}
        title="Delete knowledge base"
        message={`Delete "${shortName(deleting?.name)}"? This removes indexed vectors for this knowledge base.`}
        destructive
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

export default KnowledgeBaseList
