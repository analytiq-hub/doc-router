"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { KnowledgeBaseDocument } from '@docrouter/sdk';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
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
        <div className="flex items-center h-full w-full">
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
    </div>
  );
};

export default KnowledgeBaseDocuments;
