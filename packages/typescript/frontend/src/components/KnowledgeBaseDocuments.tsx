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
  const [chunks, setChunks] = useState<KBChunk[]>([]);
  const [isLoadingChunks, setIsLoadingChunks] = useState(false);
  const [chunksDialogOpen, setChunksDialogOpen] = useState(false);
  const [currentChunkIndex, setCurrentChunkIndex] = useState(0);

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

  const loadChunks = useCallback(async (documentId: string) => {
    try {
      setIsLoadingChunks(true);
      const response = await docRouterOrgApi.getKBDocumentChunks({
        kbId,
        documentId,
        skip: 0,
        limit: 1000 // Load all chunks for now
      });
      setChunks(response.chunks);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading chunks';
      toast.error('Error: ' + errorMsg);
    } finally {
      setIsLoadingChunks(false);
    }
  }, [docRouterOrgApi, kbId]);

  const handleChunksClick = useCallback(async (e: React.MouseEvent, document: KnowledgeBaseDocument) => {
    e.stopPropagation(); // Prevent row click
    setSelectedDocument(document);
    setCurrentChunkIndex(0); // Start at first chunk
    setChunksDialogOpen(true);
    await loadChunks(document.document_id);
  }, [loadChunks]);

  const handlePrevChunk = useCallback(() => {
    setCurrentChunkIndex(prev => Math.max(0, prev - 1));
  }, []);

  const handleNextChunk = useCallback(() => {
    setCurrentChunkIndex(prev => Math.min(chunks.length - 1, prev + 1));
  }, [chunks.length]);

  // Keyboard navigation for chunks
  useEffect(() => {
    if (!chunksDialogOpen || chunks.length === 0) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') {
        handlePrevChunk();
      } else if (e.key === 'ArrowRight') {
        handleNextChunk();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [chunksDialogOpen, chunks.length, handlePrevChunk, handleNextChunk]);

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
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="h6">
              Chunks for {selectedDocument?.document_name}
            </Typography>
            {chunks.length > 0 && (
              <Box display="flex" alignItems="center" gap={2}>
                <IconButton
                  onClick={handlePrevChunk}
                  disabled={currentChunkIndex === 0}
                  size="small"
                >
                  <ArrowBack />
                </IconButton>
                <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500 }}>
                  Chunk {currentChunkIndex + 1} of {chunks.length}
                </Typography>
                <IconButton
                  onClick={handleNextChunk}
                  disabled={currentChunkIndex === chunks.length - 1}
                  size="small"
                >
                  <ArrowForward />
                </IconButton>
              </Box>
            )}
          </Box>
        </DialogTitle>
        <DialogContent>
          {isLoadingChunks ? (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
              <CircularProgress />
            </Box>
          ) : chunks.length === 0 ? (
            <Typography variant="body2" color="text.secondary" align="center" py={4}>
              No chunks found for this document.
            </Typography>
          ) : chunks[currentChunkIndex] ? (
            <Box>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Chip
                  label={`Chunk Index: ${chunks[currentChunkIndex].chunk_index}`}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
                <Box display="flex" gap={2}>
                  {(() => {
                    const chunk = chunks[currentChunkIndex];
                    const start = (chunk as any).char_offset_start;
                    const end = (chunk as any).char_offset_end;
                    return start != null && end != null && typeof start === 'number' && typeof end === 'number' ? (
                      <Typography variant="caption" sx={{ color: 'text.primary', fontWeight: 500 }}>
                        Characters: {start.toLocaleString()} - {end.toLocaleString()}
                      </Typography>
                    ) : null;
                  })()}
                  <Typography variant="caption" sx={{ color: 'text.primary', fontWeight: 500 }}>
                    {chunks[currentChunkIndex].token_count} tokens
                  </Typography>
                </Box>
              </Box>
              <Typography
                variant="body2"
                component="pre"
                sx={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                  lineHeight: 1.6,
                  p: 2,
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  backgroundColor: 'grey.50',
                  maxHeight: '50vh',
                  overflowY: 'auto'
                }}
              >
                {chunks[currentChunkIndex].chunk_text}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Indexed: {new Date(chunks[currentChunkIndex].indexed_at).toLocaleString()}
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
