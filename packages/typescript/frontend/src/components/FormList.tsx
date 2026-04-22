import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { Tag, Form } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';
import { DataGrid, GridColDef, GridFilterModel, GridRenderCellParams, GridSortModel } from '@mui/x-data-grid';
import { TextField, InputAdornment, IconButton, Menu, MenuItem, Tooltip, Box } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import DownloadIcon from '@mui/icons-material/Download';
import DriveFileRenameOutlineIcon from '@mui/icons-material/DriveFileRenameOutline';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import BadgeIcon from '@mui/icons-material/Badge';
import colors from 'tailwindcss/colors';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'react-toastify';
import FormNameModal from '@/components/FormNameModal';
import FormInfoModal from '@/components/FormInfoModal';
import { isColorLight } from '@/utils/colors';
import { formatLocalDate } from '@/utils/date';

const jsonStringifyForQuery = (value: unknown): string =>
  JSON.stringify(value, (_key, v) => (v instanceof Date ? v.toISOString() : v));

const GRID_NON_SORT_FILTER_FIELDS = new Set(['form_version', 'actions']);

const FormList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [forms, setForms] = useState<Form[]>([]);
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 5 });
  const [total, setTotal] = useState(0);
  const [sortModel, setSortModel] = useState<GridSortModel>([{ field: 'form_revid', sort: 'desc' }]);
  const [filterModel, setFilterModel] = useState<GridFilterModel>({ items: [] });
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedForm, setSelectedForm] = useState<Form | null>(null);
  const [isNameModalOpen, setIsNameModalOpen] = useState(false);
  const [isCloning, setIsCloning] = useState(false);
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);

  const loadForms = useCallback(async () => {
    try {
      setIsLoading(true);
      const sortForApi = sortModel.filter((s) => !GRID_NON_SORT_FILTER_FIELDS.has(s.field));
      const filterForApi: GridFilterModel = {
        ...filterModel,
        items: filterModel.items.filter((i) => !GRID_NON_SORT_FILTER_FIELDS.has(i.field)),
      };
      const response = await docRouterOrgApi.listForms({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        name_search: searchTerm || undefined,
        sort: sortForApi.length ? jsonStringifyForQuery(sortForApi) : undefined,
        filters: filterForApi.items.length ? jsonStringifyForQuery(filterForApi) : undefined,
      });
      setForms(response.forms);
      setTotal(response.total_count);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading forms';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [paginationModel, docRouterOrgApi, searchTerm, sortModel, filterModel]);

  const loadTags = useCallback(async () => {
    try {
      const response = await docRouterOrgApi.listTags({ limit: 100 });
      setAvailableTags(response.tags);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading tags';
      setMessage('Error: ' + errorMsg);
    }
  }, [docRouterOrgApi]);

  useEffect(() => {
    void loadForms();
  }, [loadForms]);

  useEffect(() => {
    void loadTags();
  }, [loadTags]);

  // Update the edit handler
  const handleEdit = (form: Form) => {
    router.push(`/orgs/${organizationId}/forms/${form.form_revid}`);
    handleMenuClose();
  };

  // Add a function to handle form name change
  const handleNameForm = (form: Form) => {
    setSelectedForm(form);
    setIsCloning(false);
    setIsNameModalOpen(true);
    handleMenuClose();
  };

  const handleNameSubmit = async (newName: string) => {
    if (!selectedForm) return;
    
    try {
      // Create a new form config with the updated name
      const formConfig = {
        name: newName,
        response_format: selectedForm.response_format
      };
      
      if (isCloning) {
        // For cloning, create a new form
        await docRouterOrgApi.createForm(formConfig);
      } else {
        // For renaming, update existing form
        await docRouterOrgApi.updateForm({
          formId: selectedForm.form_id,
          form: formConfig
        });
      }
      
      // Refresh the form list
      await loadForms();
    } catch (error) {
      console.error(`Error ${isCloning ? 'cloning' : 'renaming'} form:`, error);
      toast.error(`Failed to ${isCloning ? 'clone' : 'rename'} form`);
      throw error;
    }
  };

  // Add the missing handleDelete function
  const handleDelete = async (formId: string) => {
    try {
      setIsLoading(true);
      await docRouterOrgApi.deleteForm({ formId });
      setForms(forms.filter(form => form.form_id !== formId));
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error deleting form';
      setMessage('Error: ' + errorMsg);
      toast.error('Failed to delete form');
    } finally {
      setIsLoading(false);
      handleMenuClose();
    }
  };

  const handleCloseNameModal = () => {
    setIsNameModalOpen(false);
    setSelectedForm(null);
    setIsCloning(false);
  };

  // Add a function to handle form download
  const handleDownload = (form: Form) => {
    try {
      // Create a JSON blob from the form
      const formJson = JSON.stringify(form.response_format.json_formio, null, 2);
      const blob = new Blob([formJson], { type: 'application/json' });
      
      // Create a URL for the blob
      const url = URL.createObjectURL(blob);
      
      // Create a temporary anchor element to trigger the download
      const a = document.createElement('a');
      a.href = url;
      a.download = `${form.name.replace(/\s+/g, '_')}_form.json`;
      
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
      console.error('Error downloading form:', error);
      setMessage('Error: Failed to download form');
    }
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, form: Form) => {
    setAnchorEl(event.currentTarget);
    setSelectedForm(form);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  // Add a new function to handle clone operation
  const handleCloneOperation = (form: Form) => {
    setSelectedForm(form);
    setIsCloning(true);
    setIsNameModalOpen(true);
    handleMenuClose();
  };

  // Define columns for the data grid
  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Form Name',
      flex: 1,
      minWidth: 140,
      headerAlign: 'left',
      align: 'left',
      renderCell: (params) => (
        <div 
          className="text-blue-600 cursor-pointer hover:underline"
          onClick={() => handleEdit(params.row)}
        >
          {params.row.name}
        </div>
      ),
    },
    {
      field: 'form_version',
      headerName: 'Version',
      width: 100,
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
      headerAlign: 'left',
      align: 'left',
      renderCell: (params) => (
        <div className="text-gray-600">
          v{params.row.form_version}
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
        const formTags = availableTags.filter(tag => 
          params.row.tag_ids?.includes(tag.id)
        );
        const firstTag = formTags[0];
        const hasMoreTags = formTags.length > 1;

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
              {formTags.map(tag => tagChip(tag))}
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
      field: 'created_at',
      headerName: 'Created',
      type: 'dateTime',
      width: 200,
      headerAlign: 'left',
      align: 'left',
      valueGetter: (params: GridRenderCellParams) => {
        const anyParams = params as unknown as { row?: { created_at?: unknown }; value?: unknown };
        const v = (anyParams.row?.created_at ?? anyParams.value) as string | Date | null | undefined;
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
        const anyParams = params as unknown as { row?: { created_at?: unknown } };
        if (!anyParams?.row?.created_at) return '';
        return <div className="text-gray-600">{formatLocalDate(anyParams.row.created_at as string)}</div>;
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      headerAlign: 'center',
      align: 'center',
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
      renderCell: (params) => (
        <div>
          <IconButton
            onClick={(e) => handleMenuOpen(e, params.row)}
            disabled={isLoading}
            className="text-gray-600 hover:bg-gray-50"
          >
            <MoreVertIcon />
          </IconButton>
        </div>
      ),
    },
  ];

  return (
    <div className="p-4 mx-auto">
      <div className="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-200 text-blue-800 hidden md:block">
        <p className="text-sm">
          Forms are used to check data extracted from documents. Below is a list of your existing forms. 
          If none are available, <Link href={`/orgs/${organizationId}/forms?tab=form-create`} className="text-blue-600 font-medium hover:underline">click here</Link> or use the tab above to create a new form.
        </p>
      </div>
      <h2 className="text-xl font-bold mb-4 hidden md:block">Forms</h2>
      
      {/* Search Box */}
      <div className="mb-4">
        <TextField
          fullWidth
          variant="outlined"
          placeholder="Search forms..."
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setPaginationModel((prev) => ({ ...prev, page: 0 }));
          }}
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
          rows={forms}
          columns={columns}
          getRowId={(row) => row.form_revid}
          sortingMode="server"
          sortModel={sortModel}
          onSortModelChange={(model) => {
            setSortModel(model.filter((s) => !GRID_NON_SORT_FILTER_FIELDS.has(s.field)));
            setPaginationModel((prev) => ({ ...prev, page: 0 }));
          }}
          filterMode="server"
          filterModel={filterModel}
          onFilterModelChange={(model) => {
            setFilterModel({
              ...model,
              items: model.items.filter((i) => !GRID_NON_SORT_FILTER_FIELDS.has(i.field)),
            });
            setPaginationModel((prev) => ({ ...prev, page: 0 }));
          }}
          pageSizeOptions={[5, 10, 20]}
          disableRowSelectionOnClick
          loading={isLoading}
          paginationMode="server"
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          rowCount={total}
          sx={{
            '& .MuiDataGrid-cell': {
              padding: 'px',
            },
            '& .MuiDataGrid-row:nth-of-type(odd)': {
              backgroundColor: colors.gray[100],  // Using Tailwind colors
            },
            '& .MuiDataGrid-row:hover': {
              backgroundColor: `${colors.gray[200]} !important`,  // Using Tailwind colors
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
            if (selectedForm) handleEdit(selectedForm);
          }}
          className="flex items-center gap-2"
        >
          <EditOutlinedIcon fontSize="small" className="text-blue-600" />
          <span>Edit</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedForm) {
              setAnchorEl(null); // Close menu manually
              setIsInfoModalOpen(true);
              // Don't clear selectedForm since we're opening the info modal
            }
          }}
          className="flex items-center gap-2"
        >
          <BadgeIcon fontSize="small" className="text-blue-600" />
          <span>Properties</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedForm) handleNameForm(selectedForm);
          }}
          className="flex items-center gap-2"
        >
          <DriveFileRenameOutlineIcon fontSize="small" className="text-indigo-800" />
          <span>Rename</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedForm) handleCloneOperation(selectedForm);
          }}
          className="flex items-center gap-2"
        >
          <ContentCopyIcon fontSize="small" className="text-purple-600" />
          <span>Clone</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedForm) handleDownload(selectedForm);
          }}
          className="flex items-center gap-2"
        >
          <DownloadIcon fontSize="small" className="text-green-600" />
          <span>Download</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedForm) handleDelete(selectedForm.form_id);
          }}
          className="flex items-center gap-2"
        >
          <DeleteOutlineIcon fontSize="small" className="text-red-600" />
          <span>Delete</span>
        </MenuItem>
      </Menu>
      
      {/* Rename/Clone Modal */}
      {selectedForm && (
        <FormNameModal
          isOpen={isNameModalOpen}
          onClose={handleCloseNameModal}
          formName={isCloning ? `${selectedForm.name} (Copy)` : selectedForm.name}
          onSubmit={handleNameSubmit}
          isCloning={isCloning}
          organizationId={organizationId}
        />
      )}
      
      {/* Info Modal */}
      {selectedForm && (
        <FormInfoModal
          isOpen={isInfoModalOpen}
          onClose={() => {
            setIsInfoModalOpen(false);
            setSelectedForm(null);
          }}
          form={selectedForm}
        />
      )}
    </div>
  );
};

export default FormList;