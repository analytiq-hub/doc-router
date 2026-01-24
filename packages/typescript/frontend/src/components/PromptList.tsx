import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { Tag } from '@docrouter/sdk';
import { Prompt, Schema } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { TextField, InputAdornment, IconButton, Menu, MenuItem, Autocomplete, Tooltip, Box } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DownloadIcon from '@mui/icons-material/Download';
import DriveFileRenameOutlineIcon from '@mui/icons-material/DriveFileRenameOutline';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import BadgeIcon from '@mui/icons-material/Badge';
import colors from 'tailwindcss/colors';
import { isColorLight } from '@/utils/colors';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import PromptNameModal from './PromptNameModal';
import PromptInfoModal from './PromptInfoModal';

// Define default model constant
const DEFAULT_LLM_MODEL = 'gemini-2.0-flash';

const PromptList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [availableSchemas, setAvailableSchemas] = useState<Schema[]>([]);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(5);
  const [total, setTotal] = useState(0);
  
  // Add state for menu
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedPrompt, setSelectedPrompt] = useState<Prompt | null>(null);
  const [isNameModalOpen, setIsNameModalOpen] = useState(false);
  const [isCloning, setIsCloning] = useState(false);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);

  const loadPrompts = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await docRouterOrgApi.listPrompts({
        skip: page * pageSize,
        limit: pageSize,
        nameSearch: searchTerm || undefined,
        tag_ids: selectedTagIds.length ? selectedTagIds.join(',') : undefined
      });
      setPrompts(response.prompts);
      setTotal(response.total_count);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading prompts';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, docRouterOrgApi, searchTerm, selectedTagIds]);

  const loadTags = useCallback(async () => {
    try {
      const response = await docRouterOrgApi.listTags({ limit: 100 });
      setAvailableTags(response.tags);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading tags';
      setMessage('Error: ' + errorMsg);
    }
  }, [docRouterOrgApi]);

  const loadSchemas = useCallback(async () => {
    try {
      const response = await docRouterOrgApi.listSchemas({ limit: 100 });
      setAvailableSchemas(response.schemas);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading schemas';
      setMessage('Error: ' + errorMsg);
    }
  }, [docRouterOrgApi]);

  useEffect(() => {
    // Load all required data at once
    const loadData = async () => {
      setIsLoading(true);
      try {
        await Promise.all([loadPrompts(), loadTags(), loadSchemas()]);
      } finally {
        setIsLoading(false);
      }
    };
    
    loadData();
  }, [loadPrompts, loadTags, loadSchemas]);

  // Menu handlers
  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, prompt: Prompt) => {
    setAnchorEl(event.currentTarget);
    setSelectedPrompt(prompt);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    if (!isNameModalOpen && !isInfoModalOpen) {
      setSelectedPrompt(null);
    }
  };

  // Update the edit handler
  const handleEdit = (prompt: Prompt) => {
    router.push(`/orgs/${organizationId}/prompts/${prompt.prompt_revid}`);
    handleMenuClose();
  };

  // Add rename handler
  const handleRenamePrompt = (prompt: Prompt) => {
    setSelectedPrompt(prompt);
    setIsNameModalOpen(true);
    setAnchorEl(null);
  };

  // Add clone handler
  const handleClonePrompt = (prompt: Prompt) => {
    setSelectedPrompt(prompt);
    setIsCloning(true);
    setIsNameModalOpen(true);
    setAnchorEl(null);
  };

  const handleRenameSubmit = async (newName: string) => {
    if (!selectedPrompt) return;
    
    try {
      // Create a prompt config with the updated name
      const promptConfig = {
        name: newName,
        content: selectedPrompt.content,
        schema_id: selectedPrompt.schema_id,
        schema_version: selectedPrompt.schema_version,
        tag_ids: selectedPrompt.tag_ids,
        model: selectedPrompt.model
      };
      
      if (isCloning) {
        // For cloning, create a new prompt
        await docRouterOrgApi.createPrompt({ prompt: promptConfig });
      } else {
        // For renaming, update existing prompt
        await docRouterOrgApi.updatePrompt({
          promptId: selectedPrompt.prompt_id,
          prompt: promptConfig
        });
      }
      
      // Refresh the prompt list to show the updated name
      await loadPrompts();
    } catch (error) {
      console.error(`Error ${isCloning ? 'cloning' : 'renaming'} prompt:`, error);
      throw error;
    }
  };

  const handleCloseNameModal = () => {
    setIsNameModalOpen(false);
    setSelectedPrompt(null);
    setIsCloning(false);
  };

  const handleDelete = async (promptId: string) => {
    try {
      setIsLoading(true);
      await docRouterOrgApi.deletePrompt({ promptId });
      setPrompts(prompts.filter(prompt => prompt.prompt_id !== promptId));
      handleMenuClose();
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error deleting prompt';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  // Add download handler
  const handleDownload = async (prompt: Prompt) => {
    try {
      setIsLoading(true);
      let schema;

      // Fetch the schema using schema_id instead of name+version
      if (prompt.schema_id && prompt.schema_version) {
        // Find schema with matching schema_id and version from preloaded schemas
        const matchingSchema = availableSchemas.find(
          schema => schema.schema_id === prompt.schema_id
        );
        
        if (!matchingSchema) {
          console.warn('Could not find matching schema:', prompt.schema_id, prompt.schema_version);
          setMessage('Warning: Could not find the referenced schema for download');
          return;
        }

        // Fetch the full schema details
        schema = await docRouterOrgApi.getSchema({
          schemaRevId: matchingSchema.schema_revid
        });
      }
      
      // Create export format with template support
      const promptExport = {
        name: prompt.name,
        model: prompt.model || DEFAULT_LLM_MODEL,
        tags: prompt.tag_ids?.map(id => {
          const tag = availableTags.find(t => t.id === id);
          return tag ? tag.name : null;
        }) || [],
        content: prompt.content,
        schema: schema ? {
          name: schema.name,
          response_format: schema.response_format
        } : null,
      };
      
      // Convert to JSON string with pretty formatting
      const promptJson = JSON.stringify(promptExport, null, 2);
      
      // Create a blob from the JSON string
      const blob = new Blob([promptJson], { type: 'application/json' });
      
      // Create a URL for the blob
      const url = URL.createObjectURL(blob);
      
      // Create a temporary anchor element to trigger the download
      const a = document.createElement('a');
      a.href = url;
      a.download = `${prompt.name.replace(/\s+/g, '_')}_v${prompt.prompt_version}.json`;
      
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
      console.error('Error downloading prompt:', error);
      setMessage('Error: Failed to download prompt');
    } finally {
      setIsLoading(false);
    }
  };

  // Synchronous schema name lookup from preloaded schemas
  const getSchemaName = (schemaId: string, schemaVersion: number) => {
    if (!schemaId || !schemaVersion) return '-';

    console.log('getSchemaName', schemaId, schemaVersion);
    
    const schema = availableSchemas.find(
      s => s.schema_id === schemaId
    );

    console.log('getSchemaName2', schema);
    return schema ? schema.name : '-';
  };

  // Add filtered prompts (now also filters by selected tags)
  const filteredPrompts = prompts;

  // Define columns for the data grid
  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Prompt',
      flex: 1,
      headerAlign: 'left',
      align: 'left',
      renderCell: (params) => (
        <div 
          className="text-blue-600 cursor-pointer hover:underline flex items-center h-full"
          onClick={() => handleEdit(params.row)}
        >
          {params.row.name}
        </div>
      ),
    },
    {
      field: 'prompt_version',
      headerName: 'Version',
      width: 100,
      headerAlign: 'left',
      align: 'left',
      renderCell: (params) => (
        <div className="text-gray-600 flex items-center h-full">
          v{params.row.prompt_version}
        </div>
      ),
    },
    {
      field: 'schema_id',
      headerName: 'Schema',
      width: 150,
      headerAlign: 'left',
      align: 'left',
      renderCell: (params) => {
        // Retrieve schema name using schema_id and schema_version from preloaded schemas
        const schemaName = getSchemaName(params.row.schema_id, params.row.schema_version);
        return (
          <div className="text-gray-600 flex items-center h-full">
            {(params.row.schema_id && (schemaName !== '-')) 
              ? `${schemaName}:v${params.row.schema_version}`
              : '-'}
          </div>
        );
      },
    },
    {
      field: 'model',
      headerName: 'Model',
      width: 150,
      headerAlign: 'left',
      align: 'left',
      renderCell: (params) => (
        <div className="text-gray-600 flex items-center h-full">
          {params.row.model || DEFAULT_LLM_MODEL}
        </div>
      ),
    },
    {
      field: 'tag_ids',
      headerName: 'Tags',
      width: 200,
      headerAlign: 'left',
      align: 'left',
      renderCell: (params) => {
        const promptTags = availableTags.filter(tag => 
          params.row.tag_ids?.includes(tag.id)
        );
        const firstTag = promptTags[0];
        const hasMoreTags = promptTags.length > 1;

        const tagChip = (tag: Tag) => (
          <div
            key={tag.id}
            className={`px-2 py-1 rounded text-xs ${
              isColorLight(tag.color) ? 'text-gray-800' : 'text-white'
            } flex items-center`}
            style={{ backgroundColor: tag.color }}
          >
            {tag.name}
          </div>
        );

        if (!firstTag) {
          return <div className="text-gray-400 flex items-center h-full">-</div>;
        }

        const content = (
          <div className="flex gap-1 items-center h-full">
            {tagChip(firstTag)}
            {hasMoreTags && (
              <span className="text-gray-500 text-sm">...</span>
            )}
          </div>
        );

        if (hasMoreTags) {
          const tooltipContent = (
            <Box className="flex flex-col gap-1.5 p-1">
              {promptTags.map(tag => tagChip(tag))}
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
              <div className="w-full flex items-center h-full">
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
      headerAlign: 'left',
      align: 'left',
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
    <div className="p-4 w-full">
      {/* Prompts List */}
      <div className="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-200 text-blue-800 hidden md:block">
        <p className="text-sm">
          Prompts define extraction instructions for your documents. They can be linked to schemas to ensure structured output format. 
          If none are available, <Link href={`/orgs/${organizationId}/prompts?tab=prompt-create`} className="text-blue-600 font-medium hover:underline">click here</Link> or use the tab above to create a new prompt.
        </p>
      </div>
      <h2 className="text-xl font-bold mb-4">Prompts</h2>
      
      {/* Filters */}
      <div className="mb-4 flex flex-col md:flex-row md:items-center gap-2">
        {/* Search Box */}
        <div className="flex-1">
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Search prompts..."
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
        {/* Tag Filter */}
        <div className="w-full md:w-72">
          <Autocomplete
            multiple
            options={availableTags}
            disableCloseOnSelect
            getOptionLabel={(option) => option.name}
            value={availableTags.filter(tag => selectedTagIds.includes(tag.id))}
            onChange={(_, value) => setSelectedTagIds(value.map(tag => tag.id))}
            renderInput={(params) => (
              <TextField
                {...params}
                variant="outlined"
                placeholder="Filter by tags..."
              />
            )}
            renderOption={(props, option) => (
              <li {...props} key={option.id}>
                <div
                  className={`px-2 py-1 rounded text-sm ${
                    isColorLight(option.color) ? 'text-gray-800' : 'text-white'
                  }`}
                  style={{ backgroundColor: option.color }}
                >
                  {option.name}
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
            isOptionEqualToValue={(option, value) => option.id === value.id}
            className="bg-white"
          />
        </div>
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
          rows={filteredPrompts}
          columns={columns}
          getRowId={(row) => row.prompt_revid}
          initialState={{
            pagination: {
              paginationModel: { pageSize: 5 }
            },
            sorting: {
              sortModel: [{ field: 'prompt_revid', sort: 'desc' }]  // Sort by prompt_revid descending by default
            }
          }}
          pageSizeOptions={[5, 10, 20]}
          disableRowSelectionOnClick
          loading={isLoading}
          paginationMode="server"
          rowCount={total}  // Add this to show total count
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
      
        
        {/* Actions Menu */}
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleMenuClose}
        >
          <MenuItem 
            onClick={() => {
              if (selectedPrompt) handleEdit(selectedPrompt);
            }}
            className="flex items-center gap-2"
          >
            <EditOutlinedIcon fontSize="small" className="text-blue-600" />
            <span>Edit</span>
          </MenuItem>
          <MenuItem 
            onClick={() => {
              if (selectedPrompt) {
                setAnchorEl(null); // Close menu manually
                setIsInfoModalOpen(true);
                // Don't clear selectedPrompt since we're opening the info modal
              }
            }}
            className="flex items-center gap-2"
          >
            <BadgeIcon fontSize="small" className="text-blue-600" />
            <span>Properties</span>
          </MenuItem>
          <MenuItem 
            onClick={() => {
              if (selectedPrompt) handleRenamePrompt(selectedPrompt);
            }}
            className="flex items-center gap-2"
          >
            <DriveFileRenameOutlineIcon fontSize="small" className="text-indigo-800" />
            <span>Rename</span>
          </MenuItem>
          <MenuItem 
            onClick={() => {
              if (selectedPrompt) handleClonePrompt(selectedPrompt);
            }}
            className="flex items-center gap-2"
          >
            <ContentCopyIcon fontSize="small" className="text-purple-600" />
            <span>Clone</span>
          </MenuItem>
          <MenuItem 
            onClick={() => {
              if (selectedPrompt) handleDownload(selectedPrompt);
            }}
            className="flex items-center gap-2"
          >
            <DownloadIcon fontSize="small" className="text-green-600" />
            <span>Download</span>
          </MenuItem>
          <MenuItem 
            onClick={() => {
              if (selectedPrompt) handleDelete(selectedPrompt.prompt_id);
            }}
            className="flex items-center gap-2"
          >
            <DeleteOutlineIcon fontSize="small" className="text-red-600" />
            <span>Delete</span>
          </MenuItem>
        </Menu>
        
        {/* Rename/Clone Modal */}
        {selectedPrompt && (
          <PromptNameModal
            isOpen={isNameModalOpen}
            onClose={handleCloseNameModal}
            promptName={isCloning ? `${selectedPrompt.name} (Copy)` : selectedPrompt.name}
            onSubmit={handleRenameSubmit}
            isCloning={isCloning}
          />
        )}
        
        {/* Info Modal */}
        {selectedPrompt && (
          <PromptInfoModal
            isOpen={isInfoModalOpen}
            onClose={() => {
              setIsInfoModalOpen(false);
              setSelectedPrompt(null);
            }}
            prompt={selectedPrompt}
          />
        )}
      </div>
    </div>
  );
};

export default PromptList;
