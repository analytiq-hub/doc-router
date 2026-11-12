'use client'

import {
  BadgeInfo,
  Download,
  ScanText,
  Tags,
  Trash2,
  Type,
  Zap,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import type { Document } from '@docrouter/sdk'

import { useInvalidateOrgLists, useOrgAllTags, useOrgDocuments } from '@/api/orgQueries'
import { DataTable, type DataTableColumn, type PaginationModel, type SortModel } from '@/components/data-table'
import { DocumentBulkUpdate } from '@/components/DocumentBulkUpdate'
import DocumentInfoModal from '@/components/DocumentInfoModal'
import DocumentRenameModal from '@/components/DocumentRename'
import { DocumentUpdate } from '@/components/DocumentUpdate'
import { ErrorAlert } from '@/components/ErrorAlert'
import {
  activeFields,
  type FilterField,
  FilterBuilder,
  type FilterItem,
  isActiveFilter,
  withFilterFields,
} from '@/components/FilterBuilder'
import { RowActionsMenu } from '@/components/RowActionsMenu'
import { SearchInput } from '@/components/SearchInput'
import { TagCell } from '@/components/TagCell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useDebounced } from '@/lib/useDebounced'
import { DocRouterOrgApi } from '@/utils/api'
import { useOrgCapability } from '@/hooks/useOrgPermissions'
import { CAP_DOCUMENTS_WRITE, CAP_RUNS_EXECUTE } from '@/utils/orgCapabilities'
import { formatLocalDate } from '@/utils/date'
import { parseAndEncodeMetadataSearch, type DocumentListSearchParameters } from '@/utils/documentListQuery'
import { toastActionError } from '@/utils/toastActionError'

const jsonStringifyForQuery = (value: unknown): string =>
  JSON.stringify(value, (_key, v) => (v instanceof Date ? v.toISOString() : v))

const NON_SORT_FIELDS = new Set(['tag_ids', 'case_id', 'actions'])

type OrgDocumentListProps = {
  organizationId: string
  initialCaseIdFilter?: string
}

export default function OrgDocumentList({ organizationId, initialCaseIdFilter }: OrgDocumentListProps) {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])
  const invalidate = useInvalidateOrgLists(organizationId)
  const { hasCapability: canWriteDocuments } = useOrgCapability(organizationId, CAP_DOCUMENTS_WRITE)
  const { hasCapability: canExecuteRuns } = useOrgCapability(organizationId, CAP_RUNS_EXECUTE)

  const [pagination, setPagination] = useState<PaginationModel>({ page: 0, pageSize: 25 })
  const [sortModel, setSortModel] = useState<SortModel>([{ field: 'upload_date', sort: 'desc' }])
  const [filters, setFilters] = useState<FilterItem[]>([])
  const [filterRequest, setFilterRequest] = useState<{ field: string } | null>(null)
  const [search, setSearch] = useState('')
  const nameSearch = useDebounced(search.trim())
  const [metadataSearch, setMetadataSearch] = useState('')
  const metadataSearchDebounced = useDebounced(metadataSearch.trim())
  const [caseIdFilter, setCaseIdFilter] = useState(initialCaseIdFilter ?? '')
  const caseIdDebounced = useDebounced(caseIdFilter.trim())

  useEffect(() => {
    setCaseIdFilter(initialCaseIdFilter ?? '')
  }, [initialCaseIdFilter])

  const activeFilters = filters.filter(isActiveFilter)
  const sortForApi = sortModel.filter((s) => !NON_SORT_FIELDS.has(s.field))
  const metadataForApi = metadataSearchDebounced
    ? parseAndEncodeMetadataSearch(metadataSearchDebounced) || undefined
    : undefined
  const filtersForApi = activeFilters.length ? jsonStringifyForQuery({ items: activeFilters }) : undefined
  const sortForApiStr = sortForApi.length ? jsonStringifyForQuery(sortForApi) : undefined

  const documentsQuery = useOrgDocuments(organizationId, {
    skip: pagination.page * pagination.pageSize,
    limit: pagination.pageSize,
    nameSearch: nameSearch || undefined,
    metadataSearch: metadataForApi,
    caseId: caseIdDebounced || undefined,
    sort: sortForApiStr,
    filters: filtersForApi,
  })

  const tagsQuery = useOrgAllTags(organizationId)
  const tags = tagsQuery.data ?? []
  const tagsById = useMemo(() => new Map(tags.map((tag) => [tag.id, tag])), [tags])

  const [editingDocument, setEditingDocument] = useState<Document | null>(null)
  const [isTagEditorOpen, setIsTagEditorOpen] = useState(false)
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false)
  const [infoDocument, setInfoDocument] = useState<Document | null>(null)
  const [isBulkUpdateOpen, setIsBulkUpdateOpen] = useState(false)

  const refreshList = () => void invalidate.documents()

  const bulkSearchParameters = useMemo<DocumentListSearchParameters>(
    () => ({
      searchTerm: nameSearch,
      selectedTagFilters: [],
      metadataSearch: metadataSearchDebounced,
      caseIdFilter: caseIdDebounced || undefined,
      paginationModel: pagination,
      sort: sortForApiStr,
      filters: filtersForApi,
    }),
    [
      nameSearch,
      metadataSearchDebounced,
      caseIdDebounced,
      pagination,
      sortForApiStr,
      filtersForApi,
    ],
  )

  const handleRerunOCR = async (docId: string) => {
    try {
      await docRouterOrgApi.runOCR({ documentId: docId })
      toast.info('OCR requeued')
      refreshList()
    } catch (error) {
      console.error('Error rerunning OCR:', error)
      toastActionError('Failed to rerun OCR', error)
    }
  }

  const handleDeleteFile = async (fileId: string) => {
    try {
      await docRouterOrgApi.deleteDocument({ documentId: fileId })
      refreshList()
    } catch (error) {
      console.error('Error deleting file:', error)
      toastActionError('Failed to delete document', error)
    }
  }

  const handleDownloadFile = async (doc: Document) => {
    try {
      const response = await docRouterOrgApi.getDocument({
        documentId: doc.id,
        fileType: 'original',
      })
      const fileName = doc.document_name || response.document_name
      if (response.content == null) {
        throw new Error('Document content not available')
      }
      const serverType: string | undefined = response.type as string | undefined
      const blob = new Blob([response.content], { type: serverType })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = fileName
      document.body.appendChild(anchor)
      anchor.click()
      setTimeout(() => {
        document.body.removeChild(anchor)
        URL.revokeObjectURL(url)
      }, 100)
    } catch (error) {
      console.error('Error downloading file:', error)
      toastActionError('Failed to download document', error)
    }
  }

  const handleUpdateDocument = async (
    tagIds: string[],
    metadata: Record<string, string>,
    caseOptions?: { caseId: string | null; createCaseIfMissing: boolean },
  ) => {
    if (!editingDocument) return
    try {
      await docRouterOrgApi.updateDocument({
        documentId: editingDocument.id,
        tagIds,
        metadata,
        ...(caseOptions
          ? {
              caseId: caseOptions.caseId,
              createCaseIfMissing: caseOptions.createCaseIfMissing,
            }
          : {}),
      })
      refreshList()
    } catch (error) {
      console.error('Error updating document:', error)
      toastActionError('Failed to update document', error)
    }
  }

  const handleRenameSubmit = async (newName: string) => {
    if (!editingDocument) return
    try {
      await docRouterOrgApi.updateDocument({
        documentId: editingDocument.id,
        documentName: newName,
      })
      refreshList()
    } catch (error) {
      console.error('Error renaming document:', error)
      toastActionError('Failed to rename document', error)
      throw error
    }
  }

  const filterFields: FilterField[] = useMemo(
    () => [
      { field: 'document_name', label: 'Name', kind: 'text' as const },
      { field: 'uploaded_by', label: 'Uploaded by', kind: 'text' as const },
      { field: 'state', label: 'State', kind: 'text' as const },
      {
        field: 'tag_ids',
        label: 'Tags',
        kind: 'tag' as const,
        single: true,
        options: tags.map((t) => ({ value: t.name, label: t.name })),
      },
      { field: 'upload_date', label: 'Upload date', kind: 'date' as const },
    ],
    [tags],
  )

  const columns: DataTableColumn<Document>[] = [
    {
      field: 'document_name',
      headerName: 'Document name',
      flex: 2,
      minWidth: 180,
      renderCell: ({ row }) => (
        <Link
          to={`/orgs/${organizationId}/docs/${row.id}`}
          className="text-primary hover:underline"
          title={row.document_name}
        >
          {row.document_name}
        </Link>
      ),
    },
    {
      field: 'upload_date',
      headerName: 'Upload date',
      width: 130,
      renderCell: ({ row }) =>
        row.upload_date ? (
          <span className="text-sm text-muted-foreground">{formatLocalDate(String(row.upload_date))}</span>
        ) : (
          ''
        ),
    },
    {
      field: 'uploaded_by',
      headerName: 'Uploaded by',
      flex: 1,
      minWidth: 120,
      renderCell: ({ row }) => (
        <span className="truncate text-sm" title={row.uploaded_by}>
          {row.uploaded_by}
        </span>
      ),
    },
    {
      field: 'case_id',
      headerName: 'Case',
      width: 140,
      sortable: false,
      renderCell: ({ row }) => {
        const cid = row.case_id
        if (!cid) return <span className="text-muted-foreground">—</span>
        return (
          <Link
            to={`/orgs/${organizationId}/cases/${encodeURIComponent(cid)}`}
            className="truncate font-mono text-xs text-primary hover:underline"
            title={cid}
          >
            {cid}
          </Link>
        )
      },
    },
    {
      field: 'state',
      headerName: 'State',
      width: 100,
      renderCell: ({ row }) => (
        <span className="text-sm" title={row.state ?? undefined}>
          {row.state?.replaceAll('_', ' ') ?? '—'}
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
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      hideable: false,
      resizable: false,
      renderCell: ({ row }) => (
        <RowActionsMenu
          label={row.document_name}
          actions={[
            canWriteDocuments && {
              label: 'Rename',
              icon: Type,
              onSelect: () => {
                setEditingDocument(row)
                setIsRenameModalOpen(true)
              },
            },
            { label: 'Properties', icon: BadgeInfo, onSelect: () => setInfoDocument(row) },
            canWriteDocuments && {
              label: 'Edit tags & metadata',
              icon: Tags,
              onSelect: () => {
                setEditingDocument(row)
                setIsTagEditorOpen(true)
              },
            },
            { label: 'Download', icon: Download, onSelect: () => void handleDownloadFile(row) },
            canExecuteRuns && {
              label: 'Rerun OCR',
              icon: ScanText,
              onSelect: () => void handleRerunOCR(row.id),
            },
            canWriteDocuments && {
              label: 'Delete',
              icon: Trash2,
              destructive: true,
              onSelect: () => void handleDeleteFile(row.id),
            },
          ]}
        />
      ),
    },
  ]

  const uploadTabHref = `/orgs/${organizationId}/docs?tab=upload${
    caseIdDebounced ? `&case_id=${encodeURIComponent(caseIdDebounced)}` : ''
  }`

  return (
    <>
      <div className="flex flex-col gap-4">
        <div className="rounded-lg border border-primary/25 bg-primary-soft p-4 text-sm text-foreground">
          Welcome! Upload your documents to begin transforming unstructured data into structured insights. If no documents
          are visible,{' '}
          <Link to={uploadTabHref} className="font-medium text-primary hover:underline">
            click here
          </Link>{' '}
          or use the tab above to upload and start extracting key data fields effortlessly.
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <SearchInput
            value={search}
            onChange={(value) => {
              setSearch(value)
              setPagination((p) => ({ ...p, page: 0 }))
            }}
            placeholder="Search documents..."
          />
          <Input
            className="h-9 w-64 max-w-full shrink-0"
            placeholder="Metadata (key=value,...)"
            aria-label="Search document metadata"
            value={metadataSearch}
            onChange={(e) => {
              setMetadataSearch(e.target.value)
              setPagination((p) => ({ ...p, page: 0 }))
            }}
          />
          <Input
            className="h-9 w-44 max-w-full shrink-0 font-mono text-sm"
            placeholder="Filter by case ID"
            aria-label="Filter by case ID"
            value={caseIdFilter}
            onChange={(e) => {
              setCaseIdFilter(e.target.value)
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
          {canWriteDocuments && (
            <Button className="shrink-0" onClick={() => setIsBulkUpdateOpen(true)} data-tour="document-actions">
              <Zap data-icon="inline-start" />
              Actions
            </Button>
          )}
        </div>
        <ErrorAlert error={documentsQuery.error} />
        <div className="h-150 min-h-[24rem]">
          <DataTable
            aria-label="Documents"
            rows={documentsQuery.data?.documents ?? []}
            getRowId={(row) => row.id}
            columns={withFilterFields(columns, filterFields)}
            activeFilterFields={activeFields(filters)}
            onFilterColumn={(field) => setFilterRequest({ field })}
            rowCount={documentsQuery.data?.total_count ?? 0}
            loading={documentsQuery.isFetching}
            paginationModel={pagination}
            onPaginationModelChange={setPagination}
            sortModel={sortModel}
            onSortModelChange={(model) =>
              setSortModel(model.filter((s) => !NON_SORT_FIELDS.has(s.field)))
            }
            pageSizeOptions={[10, 25, 50, 100]}
          />
        </div>
      </div>

      {editingDocument && (
        <DocumentUpdate
          isOpen={isTagEditorOpen}
          onClose={() => {
            setIsTagEditorOpen(false)
            setEditingDocument(null)
          }}
          documentName={editingDocument.document_name}
          currentTags={editingDocument.tag_ids || []}
          currentMetadata={editingDocument.metadata || {}}
          currentCaseId={editingDocument.case_id ?? null}
          availableTags={tags}
          onSave={handleUpdateDocument}
        />
      )}

      {editingDocument && (
        <DocumentRenameModal
          isOpen={isRenameModalOpen}
          onClose={() => {
            setIsRenameModalOpen(false)
            setEditingDocument(null)
          }}
          documentName={editingDocument.document_name}
          onSubmit={handleRenameSubmit}
        />
      )}

      <DocumentBulkUpdate
        isOpen={isBulkUpdateOpen}
        onClose={() => setIsBulkUpdateOpen(false)}
        organizationId={organizationId}
        availableTags={tags}
        searchParameters={bulkSearchParameters}
        onRefresh={refreshList}
      />

      {infoDocument ? (
        <DocumentInfoModal
          organizationId={organizationId}
          isOpen
          onClose={() => setInfoDocument(null)}
          document={infoDocument}
          availableTags={tags}
        />
      ) : null}
    </>
  )
}
