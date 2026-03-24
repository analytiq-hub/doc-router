"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { KnowledgeBaseDocument, KBChunk } from '@docrouter/sdk';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material';
import colors from 'tailwindcss/colors';
import { toast } from 'react-toastify';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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

      {/* Chunks Dialog */}
      <Dialog
        open={chunksDialogOpen}
        onClose={() => setChunksDialogOpen(false)}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: {
            height: '75vh',
            maxHeight: '75vh',
            display: 'flex',
            flexDirection: 'column'
          }
        }}
      >
        <DialogTitle className="!flex !flex-row !items-start sm:!items-center !justify-between !gap-3 !pr-10">
          <h2 className="text-lg font-semibold text-gray-900 leading-snug min-w-0 flex-1">
            Chunks for{' '}
            <span className="break-words">{selectedDocument?.document_name}</span>
          </h2>
          {chunkTotalCount > 0 ? (
            <div
              className="inline-flex shrink-0 items-stretch rounded-lg border border-gray-300 bg-white shadow-sm overflow-hidden"
              role="group"
              aria-label="Chunk navigation"
            >
              <button
                type="button"
                onClick={handlePrevChunk}
                disabled={atFirstChunk || chunkNavDisabled}
                className="flex h-9 w-9 items-center justify-center text-gray-700 hover:bg-gray-100 disabled:opacity-35 disabled:pointer-events-none transition-colors"
                aria-label="Previous chunk"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <div className="w-px self-stretch bg-gray-200" aria-hidden />
              <div className="flex min-w-0 items-center gap-1.5 bg-gray-50/80 px-2">
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
                  aria-label="Chunk number (1-based, press Enter to go)"
                  className="h-9 w-[4.75rem] shrink-0 border-0 bg-transparent px-1 text-center text-sm font-semibold text-gray-900 tabular-nums outline-none ring-0 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-blue-400/60 disabled:opacity-50 rounded-sm"
                />
                <span className="text-xs font-medium text-gray-500 whitespace-nowrap tabular-nums">
                  of {chunkTotalCount.toLocaleString()}
                </span>
              </div>
              <div className="w-px self-stretch bg-gray-200" aria-hidden />
              <button
                type="button"
                onClick={handleNextChunk}
                disabled={atLastChunk || chunkNavDisabled}
                className="flex h-9 w-9 items-center justify-center text-gray-700 hover:bg-gray-100 disabled:opacity-35 disabled:pointer-events-none transition-colors"
                aria-label="Next chunk"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          ) : null}
        </DialogTitle>
        <DialogContent className="!flex !flex-1 !flex-col !min-h-0 !overflow-y-auto !pt-4">
          {isLoadingChunk && !displayChunk ? (
            <div className="flex min-h-[200px] items-center justify-center">
              <div
                className="h-9 w-9 animate-spin rounded-full border-2 border-gray-200 border-t-blue-600"
                aria-hidden
              />
            </div>
          ) : !isLoadingChunk && chunkTotalCount === 0 ? (
            <p className="py-8 text-center text-sm text-gray-500">No chunks found for this document.</p>
          ) : displayChunk ? (
            <div className={`relative flex min-h-0 flex-1 flex-col ${isLoadingChunk ? 'opacity-50' : ''}`}>
              {isLoadingChunk ? (
                <div className="pointer-events-none absolute left-1/2 top-1/2 z-[1] -translate-x-1/2 -translate-y-1/2">
                  <div
                    className="h-8 w-8 animate-spin rounded-full border-2 border-gray-200 border-t-blue-600"
                    aria-hidden
                  />
                </div>
              ) : null}
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <span className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-900">
                  Chunk Index: {displayChunk.chunk_index}
                </span>
                <div className="flex flex-wrap items-center gap-3 text-xs font-medium text-gray-700">
                  {(() => {
                    const chunk = displayChunk;
                    const start = chunk.indexed_text_start;
                    const end = chunk.indexed_text_end;
                    return start != null && end != null && typeof start === 'number' && typeof end === 'number' ? (
                      <span>
                        Characters: {start.toLocaleString()} – {end.toLocaleString()}
                      </span>
                    ) : null;
                  })()}
                  <span>{displayChunk.token_count} tokens</span>
                </div>
              </div>
              {(() => {
                const ch = displayChunk;
                const parts: string[] = [];
                if (ch.chunk_type) parts.push(`Type: ${ch.chunk_type}`);
                if (ch.page_start != null && ch.page_end != null && ch.page_start > 0) {
                  parts.push(
                    ch.page_start === ch.page_end
                      ? `Page ${ch.page_start}`
                      : `Pages ${ch.page_start}–${ch.page_end}`
                  );
                }
                if (ch.heading_path) parts.push(ch.heading_path);
                if (parts.length === 0) return null;
                return <p className="mb-2 text-sm text-gray-600">{parts.join(' · ')}</p>;
              })()}
              <div className="min-h-0 flex-1 overflow-y-auto rounded-md border border-gray-200 bg-gray-50 p-4">
                <div className="markdown-prose">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {displayChunk.chunk_text}
                  </ReactMarkdown>
                </div>
              </div>
              <p className="mt-2 text-xs text-gray-500">
                Indexed: {new Date(displayChunk.indexed_at).toLocaleString()}
              </p>
            </div>
          ) : null}
        </DialogContent>
        <DialogActions className="!border-t !border-gray-200 !px-6 !py-2">
          <button
            type="button"
            onClick={() => setChunksDialogOpen(false)}
            className="rounded-md px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
          >
            Close
          </button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

export default KnowledgeBaseDocuments;
