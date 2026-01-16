"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { Tag } from '@docrouter/sdk';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { TextField, InputAdornment, IconButton, Menu, MenuItem } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import BadgeIcon from '@mui/icons-material/Badge';
import colors from 'tailwindcss/colors';
import { isColorLight } from '@/utils/colors';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import TagInfoModal from '@/components/TagInfoModal';

const TagList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(5);
  const [total, setTotal] = useState(0);
  
  // Add state for menu
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedTag, setSelectedTag] = useState<Tag | null>(null);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);

  const loadTags = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await docRouterOrgApi.listTags({ skip: page * pageSize, limit: pageSize, nameSearch: searchTerm || undefined });
      setTags(response.tags);
      if (response.total_count !== undefined) {
        setTotal(response.total_count);
      }
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading tags';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [docRouterOrgApi, page, pageSize, searchTerm]);

  useEffect(() => {
    loadTags();
  }, [loadTags]);

  // Menu handlers
  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, tag: Tag) => {
    setAnchorEl(event.currentTarget);
    setSelectedTag(tag);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedTag(null);
  };

  const handleDelete = async (tagId: string) => {
    try {
      setIsLoading(true);
      await docRouterOrgApi.deleteTag({ tagId });
      setTags(tags.filter(tag => tag.id !== tagId));
      setMessage('Tag deleted successfully');
      handleMenuClose();
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error deleting tag';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  // Update the edit handler
  const handleEdit = (tag: Tag) => {
    router.push(`/orgs/${organizationId}/tags/${tag.id}`);
    handleMenuClose();
  };

  // Filter tags based on search term
  const filteredTags = tags.filter(tag =>
    tag.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    tag.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Define columns for the data grid
  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Tag Name',
      flex: 1,
      renderCell: (params) => {
        const bgColor = params.row.color;
        const textColor = isColorLight(bgColor) ? 'text-gray-800' : 'text-white';
        
        return (
          <div 
            className="flex items-center h-full w-full cursor-pointer"
            onClick={() => handleEdit(params.row)}
          >
            <div 
              className={`px-2 py-1 leading-none rounded shadow-sm ${textColor}`}
              style={{ 
                backgroundColor: bgColor,
              }}
            >
              {params.row.name}
            </div>
          </div>
        );
      },
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      renderCell: (params) => (
        <div className="flex items-center h-full w-full">
          {params.row.description}
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
    <div className="p-4 max-w-4xl mx-auto">
      {/* Tags List */}
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-200 text-blue-800 hidden md:block">
          <p className="text-sm">
            Tags determine which prompts are run on which documents.
            If no tags are available, <Link href={`/orgs/${organizationId}/tags?tab=tag-create`} className="text-blue-600 font-medium hover:underline">click here</Link> or use the tab above to create a new tag.
          </p>
        </div>
        <h2 className="text-xl font-bold mb-4 hidden md:block">Tags</h2>
        
        {/* Search Box */}
        <div className="mb-4">
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Search tags..."
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
        <div style={{ height: 400, width: '100%' }}>
          <DataGrid
            rows={filteredTags}
            columns={columns}
            initialState={{
              pagination: {
                paginationModel: { pageSize: 5 }
              },
              sorting: {
                sortModel: [{ field: 'id', sort: 'desc' }]
              }
            }}
            pageSizeOptions={[5, 10, 20]}
            disableRowSelectionOnClick
            loading={isLoading}
            getRowId={(row) => row.id}
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
              if (selectedTag) handleEdit(selectedTag);
            }}
            className="flex items-center gap-2"
          >
            <EditOutlinedIcon fontSize="small" className="text-blue-600" />
            <span>Edit</span>
          </MenuItem>
          <MenuItem 
            onClick={() => {
              if (selectedTag) {
                setAnchorEl(null); // Close menu manually
                setIsInfoModalOpen(true);
                // Don't clear selectedTag since we're opening the info modal
              }
            }}
            className="flex items-center gap-2"
          >
            <BadgeIcon fontSize="small" className="text-blue-600" />
            <span>Properties</span>
          </MenuItem>
          <MenuItem 
            onClick={() => {
              if (selectedTag) handleDelete(selectedTag.id);
            }}
            className="flex items-center gap-2"
          >
            <DeleteOutlineIcon fontSize="small" className="text-red-600" />
            <span>Delete</span>
          </MenuItem>
        </Menu>
        
        {/* Info Modal */}
        {selectedTag && (
          <TagInfoModal
            isOpen={isInfoModalOpen}
            onClose={() => {
              setIsInfoModalOpen(false);
              setSelectedTag(null);
            }}
            tag={selectedTag}
          />
        )}
      </div>
    </div>
  );
};

export default TagList; 