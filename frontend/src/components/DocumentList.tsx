'use client'

import React, { useState, useEffect, useCallback } from 'react';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { Box, IconButton, TextField, InputAdornment, Autocomplete, Menu, MenuItem } from '@mui/material';
import { isAxiosError } from 'axios';
import { 
  listDocumentsApi, 
  deleteDocumentApi, 
  listTagsApi,
  updateDocumentApi,
  getDocumentApi
} from '@/utils/api';
import { Tag } from '@/types/index';
import { DocumentMetadata } from '@/types/index';
import Link from 'next/link';
import DeleteIcon from '@mui/icons-material/Delete';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import DriveFileRenameOutlineIcon from '@mui/icons-material/DriveFileRenameOutline';
import DownloadIcon from '@mui/icons-material/Download';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { isColorLight } from '@/utils/colors';
import colors from 'tailwindcss/colors';
import { DocumentUpdate } from './DocumentUpdate';
import SearchIcon from '@mui/icons-material/Search';
import { toast } from 'react-toastify';
import DocumentRenameModal from './DocumentRename';
import { formatLocalDateWithTZ } from '@/utils/date';

const DocumentList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [totalRows, setTotalRows] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState(() => {
    if (typeof window !== 'undefined') {
      const isSmallScreen = window.innerWidth < 768;
      return { page: 0, pageSize: isSmallScreen ? 5 : 25 };
    }
    return { page: 0, pageSize: 25 };
  });
  const [isLoading, setIsLoading] = useState(true);
  const [tags, setTags] = useState<Tag[]>([]);
  const [editingDocument, setEditingDocument] = useState<DocumentMetadata | null>(null);
  const [isTagEditorOpen, setIsTagEditorOpen] = useState(false);
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTagFilters, setSelectedTagFilters] = useState<Tag[]>([]);

  // Add state for menu
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedDocument, setSelectedDocument] = useState<DocumentMetadata | null>(null);

  const [isSmallScreen, setIsSmallScreen] = useState(false);

  const fetchFiles = useCallback(async () => {
    try {
      setIsLoading(true);
      console.log('Fetching documents...', paginationModel);
      
      // Build query parameters for filtering
      const queryParams: Record<string, string | number | undefined> = {
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize
      };
      
      // Add search term if provided
      if (searchTerm.trim()) {
        queryParams.nameSearch = searchTerm.trim();
      }
      
      // Add tag filters if provided
      if (selectedTagFilters.length > 0) {
        queryParams.tagIds = selectedTagFilters.map(tag => tag.id).join(',');
      }
      
      const response = await listDocumentsApi({
        organizationId,
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        nameSearch: searchTerm.trim() || undefined,
        tagIds: selectedTagFilters.length > 0 ? selectedTagFilters.map(tag => tag.id).join(',') : undefined,
      });
      
      console.log('Documents response:', response);
      setDocuments(response.documents);
      setTotalRows(response.total_count);
    } catch (error: unknown) {
      console.error('Error fetching documents:', error);
      if (isAxiosError(error) && error.response?.status === 401) {
        // If unauthorized, wait a bit and retry once
        console.log('Unauthorized, waiting for token and retrying...');
        await new Promise(resolve => setTimeout(resolve, 1000));
        try {
          const retryResponse = await listDocumentsApi({
            organizationId: organizationId,
            skip: paginationModel.page * paginationModel.pageSize,
            limit: paginationModel.pageSize
          }); 
          setDocuments(retryResponse.documents);  // Changed from pdfs
          setTotalRows(retryResponse.total_count);
        } catch (retryError) {
          console.error('Retry failed:', retryError);
          setDocuments([]);
          setTotalRows(0);
        }
      } else {
        setDocuments([]);
        setTotalRows(0);
      }
    } finally {
      setIsLoading(false);
    }
  }, [paginationModel, organizationId, searchTerm, selectedTagFilters]);

  useEffect(() => {
    console.log('FileList component mounted or pagination changed');
    fetchFiles();
  }, [fetchFiles, paginationModel]);

  // Load tags once when component mounts
  useEffect(() => {
    const loadTags = async () => {
      try {
        const response = await listTagsApi({ organizationId: organizationId });
        setTags(response.tags);
      } catch (error) {
        console.error('Error loading tags:', error);
      }
    };
    loadTags();
  }, [organizationId]);

  // Menu handlers
  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, document: DocumentMetadata) => {
    setAnchorEl(event.currentTarget);
    setSelectedDocument(document);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedDocument(null);
  };

  const handleDeleteFile = async (fileId: string) => {
    try {
      await deleteDocumentApi(
        {
          organizationId: organizationId,
          documentId: fileId
        }
      );
      // Refresh the file list after deletion
      fetchFiles();
      handleMenuClose();
      toast.success('Document deleted successfully');
    } catch (error) {
      console.error('Error deleting file:', error);
      toast.error('Failed to delete document');
    }
  };

  const handleEditTags = (document: DocumentMetadata) => {
    setEditingDocument(document);
    setIsTagEditorOpen(true);
    handleMenuClose();
  };

  const handleRenameDocument = (document: DocumentMetadata) => {
    setEditingDocument(document);
    setIsRenameModalOpen(true);
    handleMenuClose();
  };

  const handleDownloadFile = async (doc: DocumentMetadata) => {
    try {
      const response = await getDocumentApi({
        organizationId: organizationId,
        documentId: doc.id,
        fileType: "original"
      });
      
      // Create a blob from the array buffer
      // Infer MIME type from file extension to avoid forcing .pdf downloads
      const fileName = doc.document_name || response.metadata.document_name;
      // Use server-reported MIME type when available
      const serverType: string | undefined = response.metadata?.type as string | undefined;
      const blob = new Blob([response.content], { type: serverType });
      
      // Create a URL for the blob
      const url = URL.createObjectURL(blob);
      
      // Create a temporary anchor element to trigger the download
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      
      // Append to the document, click, and remove
      document.body.appendChild(a);
      a.click();
      
      // Clean up
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 100);
      
      handleMenuClose();
    } catch (error) {
      console.error('Error downloading file:', error);
      toast.error('Failed to download document');
    }
  };

  const handleUpdateTags = async (tagIds: string[]) => {
    if (!editingDocument) return;
    
    try {
      console.log('DocumentList - handleUpdateTags:', {
        documentId: editingDocument.id,
        oldTags: editingDocument.tag_ids,
        newTags: tagIds
      });
      
      await updateDocumentApi(
        {
          organizationId: organizationId,
          documentId: editingDocument.id,
          tagIds: tagIds
        }
      );
      console.log('Tags updated successfully, refreshing document list');
      
      // Refresh the document list to show updated tags
      await fetchFiles();
      console.log('Document list refreshed');
    } catch (error) {
      console.error('Error updating document tags:', error);
      toast.error('Failed to update tags');
    }
  };

  const handleRenameSubmit = async (newName: string) => {
    if (!editingDocument) return;
    
    try {
      await updateDocumentApi({
        organizationId: organizationId,
        documentId: editingDocument.id,
        documentName: newName
      });
      
      // Refresh the document list to show the updated name
      await fetchFiles();
    } catch (error) {
      console.error('Error renaming document:', error);
      toast.error('Failed to rename document');
      throw error; // Rethrow to handle in the component
    }
  };

  useEffect(() => {
    const checkScreenSize = () => {
      setIsSmallScreen(window.innerWidth < 768);
    };
    
    // Initial check
    checkScreenSize();
    
    // Add event listener for window resize
    window.addEventListener('resize', checkScreenSize);
    
    // Cleanup
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  // Define all columns
  const allColumns: GridColDef[] = [
    {
      field: 'document_name',
      headerName: 'Document Name',
      flex: 2,
      renderCell: (params) => {
        return (
          <Link href={`/orgs/${organizationId}/docs/${params.row.id}`}
            style={{ color: 'blue', textDecoration: 'underline' }}>
            {params.value}
          </Link>
        );
      },
    },
    {
      field: 'upload_date',
      headerName: 'Upload Date', // Renamed column
      flex: .65, // Slightly wider than before
      valueFormatter: (params: GridRenderCellParams) => {
        if (!params.value) return '';
        return formatLocalDateWithTZ(params.value as string);
      },
      renderCell: (params: GridRenderCellParams) => {
        if (!params.value) return '';
        const formattedDate = formatLocalDateWithTZ(params.value as string);
        const date = new Date(params.value as string);
        const tooltip = date.toLocaleString();
        return (
          <div title={tooltip}>
            {formattedDate}
          </div>
        );
      },
    },
    { field: 'uploaded_by', headerName: 'Uploaded By', flex: 1 },
    { field: 'state', headerName: 'State', flex: .75 },
    {
      field: 'tag_ids',
      headerName: 'Tags',
      flex: 1,
      renderCell: (params) => {
        const documentTags = tags.filter(tag => params.row.tag_ids?.includes(tag.id));
        return (
          <div className="flex gap-1 flex-wrap items-center h-full">
            {documentTags.map(tag => {
              const bgColor = tag.color || colors.blue[500];
              const textColor = isColorLight(bgColor) ? 'text-gray-800' : 'text-white';
              return (
                <div 
                  key={tag.id}
                  className={`px-2 py-1 leading-none rounded shadow-sm ${textColor} flex items-center`}
                  style={{ backgroundColor: bgColor }}
                >
                  {tag.name}
                </div>
              );
            })}
          </div>
        );
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      renderCell: (params) => (
        <div className="flex gap-2">
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
  
  // Filter columns based on screen size
  const columns = isSmallScreen 
    ? allColumns.filter(col => ['document_name', 'tag_ids', 'actions'].includes(col.field))
    : allColumns;

  const handleCloseTagEditor = () => {
    setIsTagEditorOpen(false);
    setEditingDocument(null);
  };

  const handleCloseRenameModal = () => {
    setIsRenameModalOpen(false);
    setEditingDocument(null);
  };

  return (
    <Box sx={{ 
      flex: 1, 
      width: '100%', 
      display: 'flex', 
      flexDirection: 'column',
      height: 'calc(100vh - 184px)' // Just header + search + footer
    }}>
      <div className="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-200 text-blue-800 hidden md:block">
        <p className="text-sm">
          Welcome! Upload your documents to begin transforming unstructured data into structured insights. 
          If no documents are visible, <Link href={`/orgs/${organizationId}/docs?tab=upload`} className="text-blue-600 font-medium hover:underline">click here</Link> or use the tab above to upload and start extracting key data fields effortlessly.
        </p>
      </div>
      
      <div className="flex gap-4 mb-4">
        <TextField
          fullWidth
          variant="outlined"
          placeholder="Search documents..."
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
        <Autocomplete
          multiple
          options={tags}
          value={selectedTagFilters}
          onChange={(_, newValue) => setSelectedTagFilters(newValue)}
          getOptionLabel={(tag) => tag.name}
          renderInput={(params) => (
            <TextField
              {...params}
              variant="outlined"
              placeholder="Filter by tags..."
            />
          )}
          renderOption={(props, tag) => (
            <li {...props}>
              <div
                className={`px-2 py-1 rounded text-sm ${
                  isColorLight(tag.color) ? 'text-gray-800' : 'text-white'
                }`}
                style={{ backgroundColor: tag.color }}
              >
                {tag.name}
              </div>
            </li>
          )}
          renderTags={(tagValue, getTagProps) =>
            tagValue.map((tag, index) => {
              const { key, ...otherProps } = getTagProps({ index });
              return (
                <div
                  key={key}
                  {...otherProps}
                  className={`px-2 py-0.5 m-0.5 rounded text-sm ${
                    isColorLight(tag.color) ? 'text-gray-800' : 'text-white'
                  }`}
                  style={{ backgroundColor: tag.color }}
                >
                  {tag.name}
                </div>
              );
            })
          }
          sx={{ 
            minWidth: 300,
            '& .MuiAutocomplete-tag': {
              margin: 0,
              padding: 0
            }
          }}
        />
      </div>

      <DataGrid
        loading={isLoading}
        rows={documents} // Remove the client-side filtering here
        columns={columns}
        paginationModel={paginationModel}
        onPaginationModelChange={(newModel) => {
          setPaginationModel(newModel);
        }}
        pageSizeOptions={[5, 25, 50, 100]}
        rowCount={totalRows}
        paginationMode="server"
        disableRowSelectionOnClick
        getRowId={(row) => row.id}
        sx={{
          '& .MuiDataGrid-row:nth-of-type(odd)': {
            backgroundColor: 'rgba(0, 0, 0, 0.04)',
          },
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'rgba(0, 0, 0, 0.1)',
          },
          flex: 1,
        }}
      />
      <div>
        {isLoading ? 'Loading...' : null}
      </div>
      
      {/* Actions Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem 
          onClick={() => {
            if (selectedDocument) handleRenameDocument(selectedDocument);
          }}
          className="flex items-center gap-2"
        >
          <DriveFileRenameOutlineIcon fontSize="small" className="text-indigo-800" />
          <span>Rename</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedDocument) handleEditTags(selectedDocument);
          }}
          className="flex items-center gap-2"
        >
          <EditOutlinedIcon fontSize="small" className="text-blue-600" />
          <span>Edit Tags</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedDocument) handleDownloadFile(selectedDocument);
          }}
          className="flex items-center gap-2"
        >
          <DownloadIcon fontSize="small" className="text-green-600" />
          <span>Download</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedDocument) handleDeleteFile(selectedDocument.id);
          }}
          className="flex items-center gap-2"
        >
          <DeleteIcon fontSize="small" className="text-red-600" />
          <span>Delete</span>
        </MenuItem>
      </Menu>
      
      {/* Tag Editor Modal */}
      {editingDocument && (
        <DocumentUpdate
          isOpen={isTagEditorOpen}
          onClose={handleCloseTagEditor}
          documentName={editingDocument.document_name}
          currentTags={editingDocument.tag_ids || []}
          availableTags={tags}
          onSave={handleUpdateTags}
        />
      )}
      
      {/* Rename Modal */}
      {editingDocument && (
        <DocumentRenameModal
          isOpen={isRenameModalOpen}
          onClose={handleCloseRenameModal}
          documentName={editingDocument.document_name}
          onSubmit={handleRenameSubmit}
        />
      )}
    </Box>
  );
};

export default DocumentList;
