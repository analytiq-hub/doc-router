"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { KnowledgeBase } from '@docrouter/sdk';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { TextField, InputAdornment, IconButton, Menu, MenuItem, Chip } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import BadgeIcon from '@mui/icons-material/Badge';
import SearchOutlinedIcon from '@mui/icons-material/SearchOutlined';
import FolderIcon from '@mui/icons-material/Folder';
import colors from 'tailwindcss/colors';
import { useRouter } from 'next/navigation';
import { toast } from 'react-toastify';
import KnowledgeBaseInfoModal from '@/components/KnowledgeBaseInfoModal';

const KnowledgeBaseList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  
  // Add state for menu
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedKB, setSelectedKB] = useState<KnowledgeBase | null>(null);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);

  const loadKnowledgeBases = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await docRouterOrgApi.listKnowledgeBases({ 
        skip: page * pageSize, 
        limit: pageSize, 
        name_search: searchTerm || undefined 
      });
      setKnowledgeBases(response.knowledge_bases);
      setTotal(response.total_count);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading knowledge bases';
      setMessage('Error: ' + errorMsg);
      toast.error('Error loading knowledge bases');
    } finally {
      setIsLoading(false);
    }
  }, [docRouterOrgApi, page, pageSize, searchTerm]);

  useEffect(() => {
    loadKnowledgeBases();
  }, [loadKnowledgeBases]);

  // Menu handlers
  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, kb: KnowledgeBase) => {
    setAnchorEl(event.currentTarget);
    setSelectedKB(kb);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedKB(null);
  };

  const handleDelete = async (kbId: string) => {
    if (!confirm('Are you sure you want to delete this knowledge base? This will delete all indexed documents and vectors.')) {
      return;
    }
    
    try {
      setIsLoading(true);
      await docRouterOrgApi.deleteKnowledgeBase({ kbId });
      toast.success('Knowledge base deleted successfully');
      await loadKnowledgeBases();
      handleMenuClose();
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error deleting knowledge base';
      setMessage('Error: ' + errorMsg);
      toast.error('Failed to delete knowledge base');
    } finally {
      setIsLoading(false);
    }
  };

  const handleEdit = (kb: KnowledgeBase) => {
    router.push(`/orgs/${organizationId}/knowledge-bases?tab=edit&kbId=${kb.kb_id}`);
    handleMenuClose();
  };

  const handleSearch = (kb: KnowledgeBase) => {
    router.push(`/orgs/${organizationId}/knowledge-bases?tab=search&kbId=${kb.kb_id}`);
    handleMenuClose();
  };

  const handleViewDocuments = (kb: KnowledgeBase) => {
    router.push(`/orgs/${organizationId}/knowledge-bases?tab=documents&kbId=${kb.kb_id}`);
    handleMenuClose();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'indexing':
        return 'warning';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  // Define columns for the data grid
  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      renderCell: (params) => (
        <div 
          className="flex items-center h-full w-full cursor-pointer"
          onClick={() => handleEdit(params.row)}
        >
          <span className="font-medium">{params.row.name}</span>
        </div>
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1.5,
      renderCell: (params) => (
        <div className="flex items-center h-full w-full text-gray-600">
          {params.row.description || '-'}
        </div>
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => (
        <div className="flex items-center h-full w-full">
          <Chip 
            label={params.row.status} 
            color={getStatusColor(params.row.status) as any}
            size="small"
          />
        </div>
      ),
    },
    {
      field: 'document_count',
      headerName: 'Documents',
      width: 100,
      renderCell: (params) => (
        <div className="flex items-center h-full w-full">
          {params.row.document_count}
        </div>
      ),
    },
    {
      field: 'chunk_count',
      headerName: 'Chunks',
      width: 100,
      renderCell: (params) => (
        <div className="flex items-center h-full w-full">
          {params.row.chunk_count.toLocaleString()}
        </div>
      ),
    },
    {
      field: 'embedding_model',
      headerName: 'Model',
      width: 180,
      renderCell: (params) => (
        <div className="flex items-center h-full w-full text-sm text-gray-600">
          {params.row.embedding_model}
        </div>
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      renderCell: (params) => (
        <div className="flex gap-2 items-center h-full">
          <IconButton
            onClick={(e) => handleMenuOpen(e, params.row)}
            className="text-gray-600 hover:bg-gray-50"
          >
            <MoreVertIcon />
          </IconButton>
        </div>
      ),
    },
  ];

  return (
    <div className="p-4 max-w-7xl mx-auto">
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-200 text-blue-800 hidden md:block">
          <p className="text-sm">
            Knowledge Bases enable semantic search across your documents using vector embeddings.
            Documents are automatically indexed into knowledge bases based on their tags.
          </p>
        </div>
        <h2 className="text-xl font-bold mb-4 hidden md:block">Knowledge Bases</h2>
        
        {/* Search Box */}
        <div className="mb-4">
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Search knowledge bases..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
          />
        </div>

        {/* Message */}
        {message && (
          <div className={`mb-4 p-3 rounded ${
            message.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'
          }`}>
            {message}
          </div>
        )}

        {/* Data Grid */}
        <div style={{ height: 600, width: '100%' }}>
          <DataGrid
            rows={knowledgeBases}
            columns={columns}
            initialState={{
              pagination: {
                paginationModel: { pageSize: 10 }
              },
              sorting: {
                sortModel: [{ field: 'created_at', sort: 'desc' }]
              }
            }}
            pageSizeOptions={[5, 10, 20, 50]}
            disableRowSelectionOnClick
            loading={isLoading}
            getRowId={(row) => row.kb_id}
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
        
        {/* Actions Menu */}
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleMenuClose}
        >
          <MenuItem 
            onClick={() => {
              if (selectedKB) handleEdit(selectedKB);
            }}
            className="flex items-center gap-2"
          >
            <EditOutlinedIcon fontSize="small" className="text-blue-600" />
            <span>Edit</span>
          </MenuItem>
          <MenuItem 
            onClick={() => {
              if (selectedKB) handleViewDocuments(selectedKB);
            }}
            className="flex items-center gap-2"
          >
            <FolderIcon fontSize="small" className="text-blue-600" />
            <span>View Documents</span>
          </MenuItem>
          <MenuItem 
            onClick={() => {
              if (selectedKB) handleSearch(selectedKB);
            }}
            className="flex items-center gap-2"
          >
            <SearchOutlinedIcon fontSize="small" className="text-blue-600" />
            <span>Search</span>
          </MenuItem>
          <MenuItem 
            onClick={() => {
              if (selectedKB) {
                setAnchorEl(null);
                setIsInfoModalOpen(true);
              }
            }}
            className="flex items-center gap-2"
          >
            <BadgeIcon fontSize="small" className="text-blue-600" />
            <span>Properties</span>
          </MenuItem>
          <MenuItem 
            onClick={() => {
              if (selectedKB) handleDelete(selectedKB.kb_id);
            }}
            className="flex items-center gap-2"
          >
            <DeleteOutlineIcon fontSize="small" className="text-red-600" />
            <span>Delete</span>
          </MenuItem>
        </Menu>
        
        {/* Info Modal */}
        {selectedKB && (
          <KnowledgeBaseInfoModal
            isOpen={isInfoModalOpen}
            onClose={() => {
              setIsInfoModalOpen(false);
              setSelectedKB(null);
            }}
            kb={selectedKB}
          />
        )}
      </div>
    </div>
  );
};

export default KnowledgeBaseList;
