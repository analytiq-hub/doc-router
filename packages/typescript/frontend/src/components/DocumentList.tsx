'use client'

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { Box, IconButton, TextField, InputAdornment, Autocomplete, Menu, MenuItem } from '@mui/material';
import { isAxiosError } from 'axios';
// All API calls now use docRouterOrgApi
import { Tag, Document } from '@docrouter/sdk';
import Link from 'next/link';
import DeleteIcon from '@mui/icons-material/Delete';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import DriveFileRenameOutlineIcon from '@mui/icons-material/DriveFileRenameOutline';
import DownloadIcon from '@mui/icons-material/Download';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import BadgeIcon from '@mui/icons-material/Badge';
import { isColorLight } from '@/utils/colors';
import { DocumentUpdate } from './DocumentUpdate';
import SearchIcon from '@mui/icons-material/Search';
import { toast } from 'react-toastify';
import DocumentRenameModal from './DocumentRename';
import { formatLocalDateWithTZ } from '@/utils/date';
import { BoltIcon } from '@heroicons/react/24/outline';
import { DocumentBulkUpdate } from './DocumentBulkUpdate';
import { DocRouterOrgApi } from '@/utils/api';
import DocumentInfoModal from './DocumentInfoModal';

// Helper function to parse and URL-encode metadata search
const parseAndEncodeMetadataSearch = (searchStr: string): string | null => {
  try {
    const pairs: string[] = [];
    // Simple parsing - split by comma and then by first equals sign
    const rawPairs = searchStr.split(',');
    
    for (const rawPair of rawPairs) {
      const trimmed = rawPair.trim();
      if (!trimmed) continue;
      
      const equalIndex = trimmed.indexOf('=');
      if (equalIndex === -1) continue;
      
      const key = trimmed.substring(0, equalIndex).trim();
      const value = trimmed.substring(equalIndex + 1).trim();
      
      if (key && value) {
        // URL encode both key and value to handle special characters
        const encodedKey = encodeURIComponent(key);
        const encodedValue = encodeURIComponent(value);
        pairs.push(`${encodedKey}=${encodedValue}`);
      }
    }
    
    return pairs.length > 0 ? pairs.join(',') : null;
  } catch (error) {
    console.error('Error parsing metadata search:', error);
    return null;
  }
};

const DocumentList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [totalRows, setTotalRows] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 25 });
  const [isLoading, setIsLoading] = useState(true);
  const [tags, setTags] = useState<Tag[]>([]);
  const [editingDocument, setEditingDocument] = useState<Document | null>(null);
  const [isTagEditorOpen, setIsTagEditorOpen] = useState(false);
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTagFilters, setSelectedTagFilters] = useState<Tag[]>([]);
  const [metadataSearch, setMetadataSearch] = useState('');

  // Add state for menu
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);

  const [isSmallScreen, setIsSmallScreen] = useState(false);

  // Add state for bulk update modal
  const [isBulkUpdateOpen, setIsBulkUpdateOpen] = useState(false);

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
      
      // Add metadata search if provided
      if (metadataSearch.trim()) {
        // Parse and URL-encode metadata search to handle special characters
        const encodedMetadataSearch = parseAndEncodeMetadataSearch(metadataSearch.trim());
        if (encodedMetadataSearch) {
          queryParams.metadataSearch = encodedMetadataSearch;
        }
      }
      
      const response = await docRouterOrgApi.listDocuments({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        nameSearch: searchTerm.trim() || undefined,
        tagIds: selectedTagFilters.length > 0 ? selectedTagFilters.map(tag => tag.id).join(',') : undefined,
        metadataSearch: metadataSearch.trim() ? parseAndEncodeMetadataSearch(metadataSearch.trim()) || undefined : undefined,
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
          const retryResponse = await docRouterOrgApi.listDocuments({
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
  }, [paginationModel, searchTerm, selectedTagFilters, metadataSearch, docRouterOrgApi]);

  useEffect(() => {
    console.log('FileList component mounted or pagination changed');
    fetchFiles();
  }, [fetchFiles, paginationModel]);

  // Load tags once when component mounts
  useEffect(() => {
    const loadTags = async () => {
      try {
        const response = await docRouterOrgApi.listTags({ limit: 100 });
        setTags(response.tags);
      } catch (error) {
        console.error('Error loading tags:', error);
      }
    };
    loadTags();
  }, [docRouterOrgApi]);

  // Menu handlers
  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, document: Document) => {
    setAnchorEl(event.currentTarget);
    setSelectedDocument(document);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedDocument(null);
  };

  const handleDeleteFile = async (fileId: string) => {
    try {
      await docRouterOrgApi.deleteDocument({ documentId: fileId });
      // Refresh the file list after deletion
      fetchFiles();
      handleMenuClose();
      toast.success('Document deleted successfully');
    } catch (error) {
      console.error('Error deleting file:', error);
      toast.error('Failed to delete document');
    }
  };

  const handleEditTags = (document: Document) => {
    setEditingDocument(document);
    setIsTagEditorOpen(true);
    handleMenuClose();
  };

  const handleRenameDocument = (document: Document) => {
    setEditingDocument(document);
    setIsRenameModalOpen(true);
    handleMenuClose();
  };

  const handleDownloadFile = async (doc: Document) => {
    try {
      const response = await docRouterOrgApi.getDocument({
        documentId: doc.id,
        fileType: "original"
      });
      
      // Create a blob from the array buffer
      // Infer MIME type from file extension to avoid forcing .pdf downloads
      const fileName = doc.document_name || response.document_name;
      // Use server-reported MIME type when available
      const serverType: string | undefined = response.type as string | undefined;
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

  const handleUpdateDocument = async (tagIds: string[], metadata: Record<string, string>) => {
    if (!editingDocument) return;
    
    try {
      console.log('DocumentList - handleUpdateDocument:', {
        documentId: editingDocument.id,
        oldTags: editingDocument.tag_ids,
        newTags: tagIds,
        oldMetadata: editingDocument.metadata,
        newMetadata: metadata
      });
      
      await docRouterOrgApi.updateDocument({
        documentId: editingDocument.id,
        tagIds: tagIds,
        metadata: metadata
      });
      console.log('Document updated successfully, refreshing document list');
      
      // Refresh the document list to show updated document
      await fetchFiles();
      console.log('Document list refreshed');
    } catch (error) {
      console.error('Error updating document:', error);
      toast.error('Failed to update document');
    }
  };

  const handleRenameSubmit = async (newName: string) => {
    if (!editingDocument) return;

    try {
      await docRouterOrgApi.updateDocument({
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
      const isSmall = window.innerWidth < 768;
      setIsSmallScreen(isSmall);
      
      // Update pagination model based on screen size
      setPaginationModel(prev => ({
        ...prev,
        pageSize: isSmall ? 5 : 25
      }));
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
              const bgColor = tag.color;
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
      width: '100%',
      display: 'flex',
      flexDirection: 'column',
      height: 'calc(100vh - 200px)', // Account for header, nav, and padding
      minHeight: '400px' // Ensure minimum height
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
          renderOption={(props, tag) => {
            const { key, ...otherProps } = props;
            return (
              <li key={key} {...otherProps}>
                <div
                  className={`px-2 py-1 rounded text-sm ${
                    isColorLight(tag.color) ? 'text-gray-800' : 'text-white'
                  }`}
                  style={{ backgroundColor: tag.color }}
                >
                  {tag.name}
                </div>
              </li>
            );
          }}
          renderTags={(tagValue, getTagProps) =>
            tagValue.map((tag, index) => {
              const { key, onDelete, ...otherProps } = getTagProps({ index });
              return (
                <div
                  key={key}
                  {...otherProps}
                  className={`px-2 py-0.5 m-0.5 rounded text-sm ${
                    isColorLight(tag.color) ? 'text-gray-800' : 'text-white'
                  }`}
                  style={{ backgroundColor: tag.color }}
                  onClick={onDelete}
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
        <TextField
          fullWidth
          variant="outlined"
          placeholder="Search metadata (author=John Smith,type=invoice)..."
          value={metadataSearch}
          onChange={(e) => setMetadataSearch(e.target.value)}
          title="Format: key=value,key2=value2. Commas and equals in values are automatically handled."
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />
        <button
          onClick={() => setIsBulkUpdateOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors duration-200"
        >
          <BoltIcon className="h-5 w-5" />
          Actions
        </button>
      </div>

      <Box sx={{ flex: 1, minHeight: 0 }}>
        <DataGrid
          loading={isLoading}
          rows={documents}
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
            height: '100%',
            '& .MuiDataGrid-row:nth-of-type(odd)': {
              backgroundColor: 'rgba(0, 0, 0, 0.04)',
            },
            '& .MuiDataGrid-row:hover': {
              backgroundColor: 'rgba(0, 0, 0, 0.1)',
            },
          }}
        />
      </Box>
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
            if (selectedDocument) {
              setAnchorEl(null); // Close menu manually
              setIsInfoModalOpen(true);
              // Don't clear selectedDocument since we're opening the info modal
            }
          }}
          className="flex items-center gap-2"
        >
          <BadgeIcon fontSize="small" className="text-blue-600" />
          <span>Properties</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedDocument) handleEditTags(selectedDocument);
          }}
          className="flex items-center gap-2"
        >
          <EditOutlinedIcon fontSize="small" className="text-blue-600" />
          <span>Edit Tags & Metadata</span>
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
          currentMetadata={editingDocument.metadata || {}}
          availableTags={tags}
          document={editingDocument}
          onSave={handleUpdateDocument}
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

      {/* Bulk Update Modal */}
      <DocumentBulkUpdate
        isOpen={isBulkUpdateOpen}
        onClose={() => setIsBulkUpdateOpen(false)}
        organizationId={organizationId}
        availableTags={tags}
        searchParameters={{
          searchTerm,
          selectedTagFilters,
          metadataSearch,
          paginationModel
        }}
        onRefresh={fetchFiles}
      />
      
      {/* Info Modal */}
      {selectedDocument && (
        <DocumentInfoModal
          isOpen={isInfoModalOpen}
          onClose={() => {
            setIsInfoModalOpen(false);
            setSelectedDocument(null);
          }}
          document={selectedDocument}
          availableTags={tags}
        />
      )}
    </Box>
  );
};

export default DocumentList;
