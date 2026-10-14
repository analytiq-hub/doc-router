'use client'

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DataGrid, GridColDef, GridRenderCellParams, GridFilterModel, GridSortModel } from '@mui/x-data-grid';
import { Box, IconButton, TextField, InputAdornment, Autocomplete, Menu, MenuItem, Tooltip } from '@mui/material';
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
import { formatLocalDate } from '@/utils/date';
import { BoltIcon } from '@heroicons/react/24/outline';
import { DocumentBulkUpdate } from './DocumentBulkUpdate';
import { DocRouterOrgApi } from '@/utils/api';
import DocumentInfoModal from './DocumentInfoModal';
import { buildListDocumentsQuery } from '@/utils/documentListQuery';

const jsonStringifyForQuery = (value: unknown): string =>
  JSON.stringify(value, (_key, v) => (v instanceof Date ? v.toISOString() : v));

type DocumentListProps = {
  organizationId: string;
  /** When set, list is scoped to this case (e.g. case detail page). */
  fixedCaseId?: string;
  hideCaseFilter?: boolean;
  initialCaseIdFilter?: string;
};

const DocumentList: React.FC<DocumentListProps> = ({
  organizationId,
  fixedCaseId,
  hideCaseFilter = false,
  initialCaseIdFilter,
}) => {
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
  const [caseIdFilter, setCaseIdFilter] = useState(fixedCaseId ?? initialCaseIdFilter ?? '');
  const [sortModel, setSortModel] = useState<GridSortModel>([]);
  const [filterModel, setFilterModel] = useState<GridFilterModel>({ items: [] });

  // Add state for menu
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);

  const [isSmallScreen, setIsSmallScreen] = useState(false);

  // Add state for bulk update modal
  const [isBulkUpdateOpen, setIsBulkUpdateOpen] = useState(false);

  // Follow the case from props: a fixed case, or ?case_id= changing on client-side navigation.
  useEffect(() => {
    setCaseIdFilter(fixedCaseId ?? initialCaseIdFilter ?? '');
  }, [fixedCaseId, initialCaseIdFilter]);

  const effectiveCaseId = (fixedCaseId ?? caseIdFilter).trim();

  const fetchFiles = useCallback(async () => {
    const requestParams = buildListDocumentsQuery(
      {
        searchTerm,
        selectedTagFilters,
        metadataSearch,
        caseIdFilter: effectiveCaseId || undefined,
      },
      paginationModel.page * paginationModel.pageSize,
      paginationModel.pageSize,
      {
        sort: sortModel.length ? jsonStringifyForQuery(sortModel) : undefined,
        filters: filterModel.items.length ? jsonStringifyForQuery(filterModel) : undefined,
      }
    );

    try {
      setIsLoading(true);
      console.log('Fetching documents...', { paginationModel, requestParams });

      const response = await docRouterOrgApi.listDocuments(requestParams);
      
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
          const retryResponse = await docRouterOrgApi.listDocuments(requestParams);
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
  }, [paginationModel, searchTerm, selectedTagFilters, metadataSearch, effectiveCaseId, sortModel, filterModel, docRouterOrgApi]);

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

  const handleRerunOCR = async (docId: string) => {
    try {
      await docRouterOrgApi.runOCR({ documentId: docId });
      toast.info('OCR requeued');
      fetchFiles();
      handleMenuClose();
    } catch (error) {
      console.error('Error rerunning OCR:', error);
      toast.error('Failed to rerun OCR');
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    try {
      await docRouterOrgApi.deleteDocument({ documentId: fileId });
      fetchFiles();
      handleMenuClose();
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
      if (response.content == null) {
        throw new Error('Document content not available');
      }
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

  const handleUpdateDocument = async (
    tagIds: string[],
    metadata: Record<string, string>,
    caseOptions?: { caseId: string | null; createCaseIfMissing: boolean }
  ) => {
    if (!editingDocument) return;
    
    try {
      await docRouterOrgApi.updateDocument({
        documentId: editingDocument.id,
        tagIds: tagIds,
        metadata: metadata,
        ...(caseOptions
          ? {
              caseId: caseOptions.caseId,
              createCaseIfMissing: caseOptions.createCaseIfMissing,
            }
          : {}),
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
  /* eslint-disable react-hooks/exhaustive-deps -- handlers only use router/org id and stable state setters */
  const allColumns = useMemo<GridColDef[]>(() => [
    {
      field: 'document_name',
      headerName: 'Document Name',
      flex: 2,
      renderCell: (params) => {
        return (
          <Link href={`/orgs/${organizationId}/docs/${params.row.id}`}
            title={params.value}
            className="block truncate"
            style={{ color: 'blue', textDecoration: 'underline' }}>
            {params.value}
          </Link>
        );
      },
    },
    {
      field: 'upload_date',
      headerName: 'Upload Date', // Renamed column
      type: 'dateTime',
      flex: .65, // Slightly wider than before
      valueGetter: (value: unknown, row: { upload_date?: unknown }) => {
        const v = (row?.upload_date ?? value) as string | Date | null | undefined;
        if (!v) return null;
        if (v instanceof Date) return v;
        const d = new Date(v);
        return Number.isNaN(d.getTime()) ? null : d;
      },
      valueFormatter: (params: GridRenderCellParams) => {
        const p = params as unknown as { value?: unknown } | null;
        if (!p?.value) return '';
        const v = p.value as Date | string;
        const iso = v instanceof Date ? v.toISOString() : String(v);
        return formatLocalDate(iso);
      },
      renderCell: (params: GridRenderCellParams) => {
        const anyParams = params as unknown as { row?: { upload_date?: unknown } };
        if (!anyParams?.row?.upload_date) return '';
        const formattedDate = formatLocalDate(anyParams.row.upload_date as string);
        const tooltip = formattedDate;
        return (
          <div title={tooltip} className="flex items-center h-full w-full min-w-0">
            <span className="truncate min-w-0">{formattedDate}</span>
          </div>
        );
      },
    },
    { field: 'uploaded_by', headerName: 'Uploaded By', flex: 1 },
    {
      field: 'case_id',
      headerName: 'Case',
      flex: 0.9,
      renderCell: (params) => {
        const cid = params.row.case_id as string | null | undefined;
        if (!cid) return <span className="text-gray-400">—</span>;
        return (
          <Link
            href={`/orgs/${organizationId}/cases/${encodeURIComponent(cid)}`}
            className="text-blue-600 underline truncate"
            title={cid}
          >
            {cid}
          </Link>
        );
      },
    },
    { field: 'state', headerName: 'State', flex: .75 },
    {
      field: 'tag_ids',
      headerName: 'Tags',
      flex: 1,
      renderCell: (params) => {
        const documentTags = tags.filter(tag => params.row.tag_ids?.includes(tag.id));
        const firstTag = documentTags[0];
        const hasMoreTags = documentTags.length > 1;

        const tagChip = (tag: Tag) => {
          const bgColor = tag.color;
          const textColor = isColorLight(bgColor) ? 'text-gray-800' : 'text-white';
          return (
            <div 
              key={tag.id}
              className={`px-2 py-1 leading-none rounded shadow-sm ${textColor} flex items-center min-w-0 overflow-hidden`}
              style={{ backgroundColor: bgColor }}
              title={tag.name}
            >
              <span className="truncate min-w-0">{tag.name}</span>
            </div>
          );
        };

        if (!firstTag) {
          return <div className="text-gray-400 flex items-center h-full">-</div>;
        }

        const content = (
          <div className="flex gap-1 items-center h-full w-full min-w-0">
            {tagChip(firstTag)}
            {hasMoreTags && (
              <span className="text-gray-500 text-sm shrink-0">...</span>
            )}
          </div>
        );

        if (hasMoreTags) {
          const tooltipContent = (
            <Box className="flex flex-col gap-1.5 p-1">
              {documentTags.map(tag => tagChip(tag))}
            </Box>
          );

          return (
            <Tooltip 
              title={tooltipContent}
              arrow
              placement="top"
              enterDelay={200}
              componentsProps={{
                tooltip: {
                  sx: {
                    bgcolor: 'white',
                    color: 'text.primary',
                    border: '1px solid',
                    borderColor: 'divider',
                    padding: '4px',
                    maxWidth: '300px',
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                  },
                },
              }}
            >
              <div className="w-full flex items-center h-full min-w-0">
                {content}
              </div>
            </Tooltip>
          );
        }

        return content;
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
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
  ], [tags, organizationId]);
  /* eslint-enable react-hooks/exhaustive-deps */
  
  // Filter columns based on screen size
  const columns = useMemo(
    () => isSmallScreen
      ? allColumns.filter(col => ['document_name', 'tag_ids', 'actions'].includes(col.field))
      : allColumns,
    [isSmallScreen, allColumns]
  );

  const handleCloseTagEditor = () => {
    setIsTagEditorOpen(false);
    setEditingDocument(null);
  };

  const handleCloseRenameModal = () => {
    setIsRenameModalOpen(false);
    setEditingDocument(null);
  };

  const isCaseScopedList = Boolean(fixedCaseId);
  const filterFieldSx = isCaseScopedList
    ? {
        flex: '1 1 0%',
        minWidth: 72,
        '& .MuiInputBase-root': { height: 40 },
      }
    : {
        flex: '1 1 12rem',
        minWidth: 0,
        maxWidth: '100%',
      };

  return (
    <Box sx={{
      width: '100%',
      display: 'flex',
      flexDirection: 'column',
      height: isCaseScopedList ? 'auto' : 'calc(100vh - 200px)',
      minHeight: isCaseScopedList ? '280px' : '400px',
    }}>
      {!isCaseScopedList && (
        <div className="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-200 text-blue-800 hidden md:block">
          <p className="text-sm">
            Welcome! Upload your documents to begin transforming unstructured data into structured insights. 
            If no documents are visible, <Link href={`/orgs/${organizationId}/docs?tab=upload`} className="text-blue-600 font-medium hover:underline">click here</Link> or use the tab above to upload and start extracting key data fields effortlessly.
          </p>
        </div>
      )}
      
      <div
        className={
          isCaseScopedList
            ? 'flex flex-nowrap gap-2 mb-4 items-center w-full min-w-0'
            : 'flex flex-wrap gap-3 mb-4 items-center'
        }
      >
        <TextField
          variant="outlined"
          placeholder={isCaseScopedList ? 'Search…' : 'Search documents...'}
          size={isCaseScopedList ? 'small' : 'medium'}
          value={searchTerm}
          onChange={(e) => { setSearchTerm(e.target.value); setPaginationModel(prev => ({ ...prev, page: 0 })); }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
          sx={filterFieldSx}
        />
        <Autocomplete
          multiple
          size={isCaseScopedList ? 'small' : 'medium'}
          options={tags}
          value={selectedTagFilters}
          onChange={(_, newValue) => { setSelectedTagFilters(newValue); setPaginationModel(prev => ({ ...prev, page: 0 })); }}
          getOptionLabel={(tag) => tag.name}
          renderInput={(params) => (
            <TextField
              {...params}
              variant="outlined"
              placeholder={isCaseScopedList ? 'Tags…' : 'Filter by tags...'}
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
            ...filterFieldSx,
            '& .MuiAutocomplete-tag': {
              margin: 0,
              padding: 0,
            },
          }}
        />
        <TextField
          variant="outlined"
          size={isCaseScopedList ? 'small' : 'medium'}
          placeholder={
            isCaseScopedList ? 'Metadata…' : 'Search metadata (author=John Smith,type=invoice)...'
          }
          value={metadataSearch}
          onChange={(e) => { setMetadataSearch(e.target.value); setPaginationModel(prev => ({ ...prev, page: 0 })); }}
          title="Format: key=value,key2=value2. Commas and equals in values are automatically handled."
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize={isCaseScopedList ? 'small' : 'medium'} />
              </InputAdornment>
            ),
          }}
          sx={filterFieldSx}
        />
        {!hideCaseFilter && (
          <TextField
            variant="outlined"
            placeholder="Filter by case ID"
            value={caseIdFilter}
            onChange={(e) => {
              setCaseIdFilter(e.target.value);
              setPaginationModel((prev) => ({ ...prev, page: 0 }));
            }}
            sx={filterFieldSx}
          />
        )}
        <button
          type="button"
          onClick={() => setIsBulkUpdateOpen(true)}
          className={`inline-flex shrink-0 items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors duration-200 ${
            isCaseScopedList ? 'h-10 whitespace-nowrap' : 'w-full sm:w-auto justify-center'
          }`}
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
          sortingMode="server"
          sortModel={sortModel}
          onSortModelChange={(newModel) => {
            console.log('sortModel changed', newModel);
            setSortModel(newModel);
            setPaginationModel(prev => ({ ...prev, page: 0 }));
          }}
          filterMode="server"
          filterModel={filterModel}
          onFilterModelChange={(newModel) => {
            console.log('filterModel changed', newModel);
            setFilterModel(newModel);
            setPaginationModel(prev => ({ ...prev, page: 0 }));
          }}
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
            if (selectedDocument) handleRerunOCR(selectedDocument.id);
          }}
          className="flex items-center gap-2"
        >
          <BoltIcon style={{ width: '1.25rem', height: '1.25rem' }} className="text-orange-500" />
          <span>Rerun OCR</span>
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
          currentCaseId={editingDocument.case_id ?? null}
          availableTags={tags}
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
          caseIdFilter: effectiveCaseId || undefined,
          paginationModel,
        }}
        onRefresh={fetchFiles}
      />
      
      {/* Info Modal */}
      {selectedDocument && (
        <DocumentInfoModal
          organizationId={organizationId}
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
