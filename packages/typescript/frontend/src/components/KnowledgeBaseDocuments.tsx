'use client'

import { ChevronLeft, ChevronRight, FileText, Loader2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { KnowledgeBaseDocument, KBChunk } from '@docrouter/sdk'

import { useOrgKBDocuments } from '@/api/orgQueries'
import { DataTable, type DataTableColumn, type PaginationModel } from '@/components/data-table'
import DraggablePanel from '@/components/DraggablePanel'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DocRouterOrgApi } from '@/utils/api'
import { formatLocalDate } from '@/utils/date'
import { toastActionError } from '@/utils/toastActionError'
import { toast } from 'react-toastify'

interface KnowledgeBaseDocumentsProps {
  organizationId: string
  kbId: string
}

const KnowledgeBaseDocuments: React.FC<KnowledgeBaseDocumentsProps> = ({ organizationId, kbId }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId])
  const [pagination, setPagination] = useState<PaginationModel>({ page: 0, pageSize: 10 })
  const listParams = {
    skip: pagination.page * pagination.pageSize,
    limit: pagination.pageSize,
  }
  const documentsQuery = useOrgKBDocuments(organizationId, kbId, listParams)

  const [selectedDocument, setSelectedDocument] = useState<KnowledgeBaseDocument | null>(null)
  const [chunksDialogOpen, setChunksDialogOpen] = useState(false)
  const [chunkTotalCount, setChunkTotalCount] = useState(0)
  const [currentChunkIndex, setCurrentChunkIndex] = useState(0)
  const [displayChunk, setDisplayChunk] = useState<KBChunk | null>(null)
  const [isLoadingChunk, setIsLoadingChunk] = useState(false)
  const [chunkJumpDraft, setChunkJumpDraft] = useState('1')

  const handleChunksClick = useCallback((document: KnowledgeBaseDocument) => {
    setSelectedDocument(document)
    setCurrentChunkIndex(0)
    setChunkTotalCount(0)
    setDisplayChunk(null)
    setChunkJumpDraft('1')
    setChunksDialogOpen(true)
  }, [])

  useEffect(() => {
    if (!chunksDialogOpen) return
    setChunkJumpDraft(String(currentChunkIndex + 1))
  }, [chunksDialogOpen, currentChunkIndex])

  const applyChunkJump = useCallback(() => {
    const parsed = parseInt(chunkJumpDraft.trim(), 10)
    if (!Number.isFinite(parsed) || chunkTotalCount === 0) {
      toast.warning('Enter a valid chunk number.')
      return
    }
    if (parsed < 1 || parsed > chunkTotalCount) {
      toast.warning(`Enter a chunk number between 1 and ${chunkTotalCount.toLocaleString()}.`)
      return
    }
    setCurrentChunkIndex(parsed - 1)
  }, [chunkJumpDraft, chunkTotalCount])

  useEffect(() => {
    if (!chunksDialogOpen || !selectedDocument) return

    let cancelled = false
    void (async () => {
      setIsLoadingChunk(true)
      try {
        const response = await docRouterOrgApi.getKBDocumentChunks({
          kbId,
          documentId: selectedDocument.document_id,
          skip: currentChunkIndex,
          limit: 1,
        })
        if (cancelled) return
        setChunkTotalCount(response.total_count)
        setDisplayChunk(response.chunks[0] ?? null)
      } catch (error) {
        if (!cancelled) {
          toastActionError('Failed to load chunks', error)
          setDisplayChunk(null)
        }
      } finally {
        if (!cancelled) setIsLoadingChunk(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [chunksDialogOpen, selectedDocument, currentChunkIndex, docRouterOrgApi, kbId])

  const handlePrevChunk = useCallback(() => {
    setCurrentChunkIndex((prev) => Math.max(0, prev - 1))
  }, [])

  const handleNextChunk = useCallback(() => {
    setCurrentChunkIndex((prev) => (chunkTotalCount > 0 ? Math.min(chunkTotalCount - 1, prev + 1) : prev))
  }, [chunkTotalCount])

  useEffect(() => {
    if (!chunksDialogOpen || chunkTotalCount === 0) return

    const handleKeyDown = (e: KeyboardEvent) => {
      const t = e.target
      if (t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement) return
      if (e.key === 'ArrowLeft') handlePrevChunk()
      else if (e.key === 'ArrowRight') handleNextChunk()
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [chunksDialogOpen, chunkTotalCount, handlePrevChunk, handleNextChunk])

  const chunkNavDisabled = isLoadingChunk
  const atFirstChunk = currentChunkIndex === 0
  const atLastChunk = chunkTotalCount > 0 && currentChunkIndex >= chunkTotalCount - 1

  const columns = useMemo<DataTableColumn<KnowledgeBaseDocument>[]>(
    () => [
      {
        field: 'document_name',
        headerName: 'Document name',
        flex: 2,
        minWidth: 180,
        sortable: false,
        renderCell: ({ row }) => (
          <Link
            to={`/orgs/${organizationId}/docs/${row.document_id}`}
            className="text-primary hover:underline"
            title={row.document_name}
          >
            {row.document_name}
          </Link>
        ),
      },
      {
        field: 'chunk_count',
        headerName: 'Chunks',
        width: 120,
        sortable: false,
        renderCell: ({ row }) => (
          <button
            type="button"
            className="text-primary hover:underline tabular-nums"
            onClick={() => handleChunksClick(row)}
          >
            {row.chunk_count.toLocaleString()}
          </button>
        ),
      },
      {
        field: 'indexed_at',
        headerName: 'Indexed at',
        width: 140,
        sortable: false,
        renderCell: ({ row }) => (
          <span className="text-sm text-muted-foreground">{formatLocalDate(row.indexed_at)}</span>
        ),
      },
    ],
    [handleChunksClick, organizationId],
  )

  return (
    <div className="mx-auto max-w-6xl p-4">
      <h2 className="mb-4 text-lg font-semibold">Documents in knowledge base</h2>
      <ErrorAlert error={documentsQuery.error} />
      <div className="h-[min(600px,70vh)] min-h-64">
        <DataTable
          aria-label="Knowledge base documents"
          rows={documentsQuery.data?.documents ?? []}
          getRowId={(row) => row.document_id}
          columns={columns}
          rowCount={documentsQuery.data?.total_count ?? 0}
          loading={documentsQuery.isFetching}
          paginationModel={pagination}
          onPaginationModelChange={setPagination}
          pageSizeOptions={[10, 20, 50]}
        />
      </div>

      {chunksDialogOpen && selectedDocument ? (
        <>
          <div
            className="fixed inset-0 z-[70] bg-black/40"
            onClick={() => setChunksDialogOpen(false)}
            role="presentation"
            aria-hidden
          />
          <DraggablePanel
            open
            resetToken={`${selectedDocument.document_id}-${kbId}`}
            anchorPercent={{ x: 50, y: 50 }}
            width="min(100vw - 2rem, 56rem)"
            height="min(92vh, 900px)"
            zIndex={71}
            ariaLabel="Document chunks"
            title={
              <>
                <FileText className="size-5 shrink-0 text-primary" aria-hidden />
                <span className="truncate">Document chunks</span>
              </>
            }
            headerActions={
              <Button type="button" size="sm" onClick={() => setChunksDialogOpen(false)}>
                Close
              </Button>
            }
          >
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="shrink-0 border-b bg-card px-5 py-4">
                <div className="flex items-center justify-between gap-4">
                  <p className="min-w-0 truncate text-sm font-semibold">{selectedDocument.document_name}</p>
                  {chunkTotalCount > 0 ? (
                    <div
                      className="inline-flex shrink-0 items-center overflow-hidden rounded-lg border"
                      role="group"
                      aria-label="Chunk navigation"
                    >
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        className="rounded-none"
                        onClick={handlePrevChunk}
                        disabled={atFirstChunk || chunkNavDisabled}
                        aria-label="Previous chunk"
                      >
                        <ChevronLeft />
                      </Button>
                      <div className="flex items-center gap-1.5 px-2">
                        <Input
                          value={chunkJumpDraft}
                          onChange={(e) => setChunkJumpDraft(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault()
                              applyChunkJump()
                            }
                          }}
                          disabled={chunkNavDisabled}
                          aria-label="Chunk number (1-based, press Enter)"
                          className="h-8 w-12 border-0 bg-transparent px-0 text-center text-sm font-semibold tabular-nums shadow-none"
                        />
                        <span className="text-sm tabular-nums text-muted-foreground">
                          / {chunkTotalCount.toLocaleString()}
                        </span>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        className="rounded-none"
                        onClick={handleNextChunk}
                        disabled={atLastChunk || chunkNavDisabled}
                        aria-label="Next chunk"
                      >
                        <ChevronRight />
                      </Button>
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5 pt-4">
                {isLoadingChunk && !displayChunk ? (
                  <div className="flex min-h-[220px] items-center justify-center">
                    <Loader2 className="size-9 animate-spin text-muted-foreground" aria-hidden />
                  </div>
                ) : !isLoadingChunk && chunkTotalCount === 0 ? (
                  <p className="py-12 text-center text-sm text-muted-foreground">No chunks found for this document.</p>
                ) : displayChunk ? (
                  <div className={`relative flex min-h-0 flex-1 flex-col gap-3 ${isLoadingChunk ? 'opacity-55' : ''}`}>
                    {isLoadingChunk ? (
                      <div className="pointer-events-none absolute left-1/2 top-1/3 z-[1] -translate-x-1/2 -translate-y-1/2">
                        <Loader2 className="size-8 animate-spin text-muted-foreground" aria-hidden />
                      </div>
                    ) : null}

                    <div className="flex flex-wrap items-center gap-2 border-b pb-3">
                      <Badge variant="outline" className="tabular-nums">
                        Chunk #{displayChunk.chunk_index}
                      </Badge>
                      {displayChunk.indexed_text_start != null && displayChunk.indexed_text_end != null ? (
                        <Badge variant="secondary" className="tabular-nums">
                          {displayChunk.indexed_text_start.toLocaleString()}–
                          {displayChunk.indexed_text_end.toLocaleString()} chars
                        </Badge>
                      ) : null}
                      <Badge variant="secondary" className="tabular-nums">
                        {displayChunk.token_count.toLocaleString()} tokens
                      </Badge>
                      <span className="flex-1" />
                      <span className="text-xs tabular-nums text-muted-foreground">
                        Indexed {formatLocalDate(displayChunk.indexed_at)}
                      </span>
                    </div>

                    {(() => {
                      const ch = displayChunk
                      const tags: string[] = []
                      if (ch.chunk_type) tags.push(ch.chunk_type)
                      if (ch.page_start != null && ch.page_end != null && ch.page_start > 0) {
                        tags.push(
                          ch.page_start === ch.page_end
                            ? `Page ${ch.page_start}`
                            : `Pages ${ch.page_start}–${ch.page_end}`,
                        )
                      }
                      if (ch.heading_path) tags.push(ch.heading_path)
                      if (tags.length === 0) return null
                      return (
                        <div className="flex flex-wrap gap-1.5">
                          {tags.map((tag) => (
                            <Badge key={tag} variant="outline" className="text-xs">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      )
                    })()}

                    <div className="min-h-0 flex-1 overflow-y-auto rounded-xl bg-muted/40 p-1.5 ring-1 ring-border">
                      <div className="rounded-lg bg-card px-5 py-4 shadow-sm">
                        <div className="markdown-prose text-sm leading-relaxed text-foreground">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayChunk.chunk_text}</ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </DraggablePanel>
        </>
      ) : null}
    </div>
  )
}

export default KnowledgeBaseDocuments
