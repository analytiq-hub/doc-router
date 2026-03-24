"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { KnowledgeBaseDocument, KBChunk } from '@docrouter/sdk';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import colors from 'tailwindcss/colors';
import { toast } from 'react-toastify';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DraggablePanel from '@/components/DraggablePanel';

interface KnowledgeBaseDocumentsProps {
  organizationId: string;
  kbId: string;
}

const KnowledgeBaseDocuments: React.FC<KnowledgeBaseDocumentsProps> = ({ organizationId, kbId }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [selectedDocument, setSelectedDocument] = useState<KnowledgeBaseDocument | null>(null);
  const [chunksDialogOpen, setChunksDialogOpen] = useState(false);
  const [chunkTotalCount, setChunkTotalCount] = useState(0);
  const [currentChunkIndex, setCurrentChunkIndex] = useState(0);
  const [displayChunk, setDisplayChunk] = useState<KBChunk | null>(null);
  const [isLoadingChunk, setIsLoadingChunk] = useState(false);
  const [chunkJumpDraft, setChunkJumpDraft] = useState('1');

  const loadDocuments = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await docRouterOrgApi.listKBDocuments({
        kbId,
        skip: page * pageSize,
        limit: pageSize
      });
      setDocuments(response.documents);
      setTotal(response.total_count);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading documents';
      toast.error('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [docRouterOrgApi, kbId, page, pageSize]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleChunksClick = useCallback((e: React.MouseEvent, document: KnowledgeBaseDocument) => {
    e.stopPropagation(); // Prevent row click
    setSelectedDocument(document);
    setCurrentChunkIndex(0);
    setChunkTotalCount(0);
    setDisplayChunk(null);
    setChunkJumpDraft('1');
    setChunksDialogOpen(true);
  }, []);

  useEffect(() => {
    if (!chunksDialogOpen) return;
    setChunkJumpDraft(String(currentChunkIndex + 1));
  }, [chunksDialogOpen, currentChunkIndex]);

  const applyChunkJump = useCallback(() => {
    const parsed = parseInt(chunkJumpDraft.trim(), 10);
    if (!Number.isFinite(parsed) || chunkTotalCount === 0) {
      toast.warning('Enter a valid chunk number.');
      return;
    }
    if (parsed < 1 || parsed > chunkTotalCount) {
      toast.warning(`Enter a chunk number between 1 and ${chunkTotalCount.toLocaleString()}.`);
      return;
    }
    setCurrentChunkIndex(parsed - 1);
  }, [chunkJumpDraft, chunkTotalCount]);

  useEffect(() => {
    if (!chunksDialogOpen || !selectedDocument) return;

    let cancelled = false;
    (async () => {
      setIsLoadingChunk(true);
      try {
        const response = await docRouterOrgApi.getKBDocumentChunks({
          kbId,
          documentId: selectedDocument.document_id,
          skip: currentChunkIndex,
          limit: 1
        });
        if (cancelled) return;
        setChunkTotalCount(response.total_count);
        setDisplayChunk(response.chunks[0] ?? null);
      } catch (error) {
        if (!cancelled) {
          const errorMsg = getApiErrorMsg(error) || 'Error loading chunks';
          toast.error('Error: ' + errorMsg);
          setDisplayChunk(null);
        }
      } finally {
        if (!cancelled) setIsLoadingChunk(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [chunksDialogOpen, selectedDocument, currentChunkIndex, docRouterOrgApi, kbId]);

  const handlePrevChunk = useCallback(() => {
    setCurrentChunkIndex(prev => Math.max(0, prev - 1));
  }, []);

  const handleNextChunk = useCallback(() => {
    setCurrentChunkIndex(prev =>
      chunkTotalCount > 0 ? Math.min(chunkTotalCount - 1, prev + 1) : prev
    );
  }, [chunkTotalCount]);

  // Keyboard navigation for chunks
  useEffect(() => {
    if (!chunksDialogOpen || chunkTotalCount === 0) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const t = e.target;
      if (t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement) return;
      if (e.key === 'ArrowLeft') {
        handlePrevChunk();
      } else if (e.key === 'ArrowRight') {
        handleNextChunk();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [chunksDialogOpen, chunkTotalCount, handlePrevChunk, handleNextChunk]);

  const chunkNavDisabled = isLoadingChunk;
  const atFirstChunk = currentChunkIndex === 0;
  const atLastChunk = chunkTotalCount > 0 && currentChunkIndex >= chunkTotalCount - 1;

  const columns: GridColDef[] = [
    {
      field: 'document_name',
      headerName: 'Document Name',
      flex: 2,
      renderCell: (params) => (
        <Link
          href={`/orgs/${organizationId}/docs/${params.row.document_id}`}
          className="text-blue-600 hover:underline"
        >
          {params.row.document_name}
        </Link>
      ),
    },
    {
      field: 'chunk_count',
      headerName: 'Chunks',
      width: 120,
      renderCell: (params) => (
        <div 
          className="flex items-center h-full w-full cursor-pointer text-blue-600 hover:text-blue-800 hover:underline"
          onClick={(e) => handleChunksClick(e, params.row)}
        >
          {params.row.chunk_count.toLocaleString()}
        </div>
      ),
    },
    {
      field: 'indexed_at',
      headerName: 'Indexed At',
      width: 200,
      renderCell: (params) => (
        <div className="flex items-center h-full w-full text-sm text-gray-600">
          {new Date(params.row.indexed_at).toLocaleString()}
        </div>
      ),
    },
  ];

  return (
    <div className="p-4 max-w-7xl mx-auto">
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">Documents in Knowledge Base</h2>
        
        {documents.length === 0 && !isLoading ? (
          <div className="text-center py-8 text-gray-500">
            No documents indexed in this knowledge base yet.
          </div>
        ) : (
          <div style={{ height: 600, width: '100%' }}>
            <DataGrid
              rows={documents}
              columns={columns}
              initialState={{
                pagination: {
                  paginationModel: { pageSize: 10 }
                },
                sorting: {
                  sortModel: [{ field: 'indexed_at', sort: 'desc' }]
                }
              }}
              pageSizeOptions={[5, 10, 20, 50]}
              disableRowSelectionOnClick
              loading={isLoading}
              getRowId={(row) => row.document_id}
              paginationMode="server"
              rowCount={total}
              onPaginationModelChange={(model) => {
                setPage(model.page);
                setPageSize(model.pageSize);
              }}
              sx={{
                '& .MuiDataGrid-cell': {
                  padding: '8px',
                },
                '& .MuiDataGrid-row:nth-of-type(odd)': {
                  backgroundColor: colors.gray[100],
                },
                '& .MuiDataGrid-row:hover': {
                  backgroundColor: `${colors.gray[200]} !important`,
                },
              }}
            />
          </div>
        )}
      </div>

      {chunksDialogOpen && selectedDocument ? (
        <>
          <div
            className="fixed inset-0 z-[70] bg-slate-900/40 backdrop-blur-[2px]"
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
                <svg
                  className="h-5 w-5 shrink-0 text-blue-600"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.75}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
                </svg>
                <span className="truncate">Document chunks</span>
              </>
            }
            headerActions={
              <button
                type="button"
                onClick={() => setChunksDialogOpen(false)}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-blue-700"
              >
                Close
              </button>
            }
          >
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="shrink-0 border-b border-slate-200/90 bg-gradient-to-b from-slate-50 to-white px-5 py-3.5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      Source file
                    </p>
                    <p className="mt-1 truncate text-sm font-medium leading-snug text-slate-900">
                      {selectedDocument.document_name}
                    </p>
                  </div>
                  {chunkTotalCount > 0 ? (
                    <div
                      className="inline-flex shrink-0 items-center gap-1 rounded-[10px] bg-slate-100/95 p-1 ring-1 ring-slate-200/90"
                      role="group"
                      aria-label="Chunk navigation"
                    >
                      <button
                        type="button"
                        onClick={handlePrevChunk}
                        disabled={atFirstChunk || chunkNavDisabled}
                        className="group flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-slate-700 shadow-sm ring-1 ring-slate-200/90 transition hover:bg-slate-50 hover:ring-slate-300 active:scale-[0.97] disabled:pointer-events-none disabled:bg-slate-100/80 disabled:text-slate-300 disabled:shadow-none disabled:ring-slate-200/60"
                        aria-label="Previous chunk"
                      >
                        <svg className="h-6 w-6" viewBox="0 0 24 24" aria-hidden>
                          <path
                            fill="currentColor"
                            d="M15.41 16.59 10.83 12l4.58-4.59L14 6l-6 6 6 6 1.41-1.41z"
                          />
                        </svg>
                      </button>
                      <div className="flex items-baseline gap-1.5 px-1">
                        <input
                          type="text"
                          inputMode="numeric"
                          value={chunkJumpDraft}
                          onChange={(e) => setChunkJumpDraft(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault();
                              applyChunkJump();
                            }
                          }}
                          disabled={chunkNavDisabled}
                          aria-label="Chunk number (1-based, press Enter)"
                          className="font-inconsolata h-10 w-[5.25rem] shrink-0 rounded-lg border-0 bg-white px-2 text-center text-[1.05rem] font-semibold tabular-nums tracking-tight text-slate-900 shadow-sm ring-1 ring-slate-200/80 outline-none transition placeholder:text-slate-400 focus:ring-2 focus:ring-blue-500/40 disabled:opacity-45"
                        />
                        <span className="whitespace-nowrap pr-0.5 text-[0.7rem] font-medium tabular-nums text-slate-500">
                          / {chunkTotalCount.toLocaleString()}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={handleNextChunk}
                        disabled={atLastChunk || chunkNavDisabled}
                        className="group flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-slate-700 shadow-sm ring-1 ring-slate-200/90 transition hover:bg-slate-50 hover:ring-slate-300 active:scale-[0.97] disabled:pointer-events-none disabled:bg-slate-100/80 disabled:text-slate-300 disabled:shadow-none disabled:ring-slate-200/60"
                        aria-label="Next chunk"
                      >
                        <svg className="h-6 w-6" viewBox="0 0 24 24" aria-hidden>
                          <path
                            fill="currentColor"
                            d="M8.59 16.59 13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z"
                          />
                        </svg>
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5 pt-4">
                {isLoadingChunk && !displayChunk ? (
                  <div className="flex min-h-[220px] items-center justify-center">
                    <div
                      className="h-9 w-9 animate-spin rounded-full border-2 border-slate-200 border-t-blue-600"
                      aria-hidden
                    />
                  </div>
                ) : !isLoadingChunk && chunkTotalCount === 0 ? (
                  <p className="py-12 text-center text-sm text-slate-500">No chunks found for this document.</p>
                ) : displayChunk ? (
                  <div className={`relative flex min-h-0 flex-1 flex-col gap-3 ${isLoadingChunk ? 'opacity-55' : ''}`}>
                    {isLoadingChunk ? (
                      <div className="pointer-events-none absolute left-1/2 top-1/3 z-[1] -translate-x-1/2 -translate-y-1/2">
                        <div
                          className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-blue-600"
                          aria-hidden
                        />
                      </div>
                    ) : null}

                    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-3">
                      <dl className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                        <div className="flex items-baseline gap-2">
                          <dt className="sr-only">Chunk index</dt>
                          <dd>
                            <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200/90">
                              Index <span className="ml-1.5 font-inconsolata tabular-nums text-slate-900">{displayChunk.chunk_index}</span>
                            </span>
                          </dd>
                        </div>
                        <div className="hidden h-4 w-px bg-slate-200 sm:block" aria-hidden />
                        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600">
                          {(() => {
                            const chunk = displayChunk;
                            const start = chunk.indexed_text_start;
                            const end = chunk.indexed_text_end;
                            return start != null && end != null && typeof start === 'number' && typeof end === 'number' ? (
                              <span className="tabular-nums">
                                Chars {start.toLocaleString()}–{end.toLocaleString()}
                              </span>
                            ) : null;
                          })()}
                          <span className="tabular-nums">{displayChunk.token_count} tokens</span>
                        </div>
                      </dl>
                    </div>

                    {(() => {
                      const ch = displayChunk;
                      const parts: string[] = [];
                      if (ch.chunk_type) parts.push(ch.chunk_type);
                      if (ch.page_start != null && ch.page_end != null && ch.page_start > 0) {
                        parts.push(
                          ch.page_start === ch.page_end
                            ? `Page ${ch.page_start}`
                            : `Pages ${ch.page_start}–${ch.page_end}`
                        );
                      }
                      if (ch.heading_path) parts.push(ch.heading_path);
                      if (parts.length === 0) return null;
                      return (
                        <p className="text-[13px] leading-relaxed text-slate-600">
                          {parts.join(' · ')}
                        </p>
                      );
                    })()}

                    <div className="min-h-0 flex-1 overflow-y-auto rounded-xl bg-white p-5 shadow-[0_1px_0_0_rgba(15,23,42,0.06)] ring-1 ring-slate-200/80">
                      <div className="markdown-prose text-[15px] leading-[1.65] text-slate-800">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {displayChunk.chunk_text}
                        </ReactMarkdown>
                      </div>
                    </div>

                    <p className="text-[11px] font-medium tabular-nums text-slate-400">
                      Indexed {new Date(displayChunk.indexed_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
                    </p>
                  </div>
                ) : null}
              </div>
            </div>
          </DraggablePanel>
        </>
      ) : null}
    </div>
  );
};

export default KnowledgeBaseDocuments;
