"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { KnowledgeBaseDocument, KBChunk } from '@docrouter/sdk';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, CircularProgress, Typography, Box, Chip, IconButton } from '@mui/material';
import { ArrowBack, ArrowForward } from '@mui/icons-material';
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
    setChunksDialogOpen(true);
  }, []);

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
      if (e.key === 'ArrowLeft') {
        handlePrevChunk();
      } else if (e.key === 'ArrowRight') {
        handleNextChunk();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [chunksDialogOpen, chunkTotalCount, handlePrevChunk, handleNextChunk]);

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
        <DialogTitle>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="h6">
              Chunks for {selectedDocument?.document_name}
            </Typography>
            {chunkTotalCount > 0 && (
              <Box display="flex" alignItems="center" gap={2}>
                <IconButton
                  onClick={handlePrevChunk}
                  disabled={currentChunkIndex === 0 || isLoadingChunk}
                  size="small"
                >
                  <ArrowBack />
                </IconButton>
                <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500 }}>
                  Chunk {currentChunkIndex + 1} of {chunkTotalCount.toLocaleString()}
                </Typography>
                <IconButton
                  onClick={handleNextChunk}
                  disabled={currentChunkIndex >= chunkTotalCount - 1 || isLoadingChunk}
                  size="small"
                >
                  <ArrowForward />
                </IconButton>
              </Box>
            )}
          </Box>
        </DialogTitle>
        <DialogContent
          sx={{
            flex: '1 1 auto',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            paddingTop: 2
          }}
        >
          {isLoadingChunk && !displayChunk ? (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
              <CircularProgress />
            </Box>
          ) : !isLoadingChunk && chunkTotalCount === 0 ? (
            <Typography variant="body2" color="text.secondary" align="center" py={4}>
              No chunks found for this document.
            </Typography>
          ) : displayChunk ? (
            <Box sx={{ position: 'relative', opacity: isLoadingChunk ? 0.5 : 1 }}>
              {isLoadingChunk ? (
                <Box
                  sx={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    zIndex: 1
                  }}
                >
                  <CircularProgress size={32} />
                </Box>
              ) : null}
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Chip
                  label={`Chunk Index: ${displayChunk.chunk_index}`}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
                <Box display="flex" flexWrap="wrap" gap={2} alignItems="center">
                  {(() => {
                    const chunk = displayChunk;
                    const start = chunk.indexed_text_start;
                    const end = chunk.indexed_text_end;
                    return start != null && end != null && typeof start === 'number' && typeof end === 'number' ? (
                      <Typography variant="caption" sx={{ color: 'text.primary', fontWeight: 500 }}>
                        Characters: {start.toLocaleString()} - {end.toLocaleString()}
                      </Typography>
                    ) : null;
                  })()}
                  <Typography variant="caption" sx={{ color: 'text.primary', fontWeight: 500 }}>
                    {displayChunk.token_count} tokens
                  </Typography>
                </Box>
              </Box>
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
                return (
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    {parts.join(' · ')}
                  </Typography>
                );
              })()}
              <Box
                sx={{
                  p: 2,
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  backgroundColor: 'grey.50',
                  flex: '1 1 auto',
                  overflowY: 'auto',
                  minHeight: 0
                }}
              >
                <div className="markdown-prose">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {displayChunk.chunk_text}
                  </ReactMarkdown>
                </div>
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Indexed: {new Date(displayChunk.indexed_at).toLocaleString()}
              </Typography>
            </Box>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setChunksDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

export default KnowledgeBaseDocuments;
