import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { Schema, SchemaResponseFormat, SchemaProperty } from '@docrouter/sdk';
import { SchemaField } from '@/types/ui';
import { getApiErrorMsg } from '@/utils/api';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { TextField, InputAdornment, Menu, MenuItem } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import DownloadIcon from '@mui/icons-material/Download';
import DriveFileRenameOutlineIcon from '@mui/icons-material/DriveFileRenameOutline';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import InfoIcon from '@mui/icons-material/Info';
import colors from 'tailwindcss/colors';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'react-toastify';
import SchemaNameModal from './SchemaNameModal';
import SchemaInfoModal from './SchemaInfoModal';

const SchemaList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(5);
  const [total, setTotal] = useState(0);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedSchema, setSelectedSchema] = useState<Schema | null>(null);
  const [isNameModalOpen, setIsNameModalOpen] = useState(false);
  const [isCloning, setIsCloning] = useState(false);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);

  const loadSchemas = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await docRouterOrgApi.listSchemas({
        skip: page * pageSize,
        limit: pageSize,
        nameSearch: searchTerm || undefined
      });
      setSchemas(response.schemas);
      setTotal(response.total_count);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading schemas';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, docRouterOrgApi, searchTerm]);

  const handleDelete = async (schemaId: string) => {
    try {
      setIsLoading(true);
      await docRouterOrgApi.deleteSchema({ schemaId });
      setSchemas(schemas.filter(schema => schema.schema_id !== schemaId));
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error deleting schema';
      setMessage('Error: ' + errorMsg);
      toast.error('Failed to delete schema');
    } finally {
      setIsLoading(false);
      handleMenuClose();
    }
  };

  useEffect(() => {
    loadSchemas();
  }, [loadSchemas]);

  // Update the edit handler
  const handleEdit = (schema: Schema) => {
    router.push(`/orgs/${organizationId}/schemas/${schema.schema_revid}`);
    handleMenuClose();
  };

  // Add a function to handle schema name change
  const handleNameSchema = (schema: Schema) => {
    setSelectedSchema(schema);
    setIsCloning(false);
    setIsNameModalOpen(true);
    handleMenuClose();
  };

  const handleNameSubmit = async (newName: string) => {
    if (!selectedSchema) return;
    
    try {
      // Create a new schema config with the updated name
      const schemaConfig = {
        name: newName,
        response_format: selectedSchema.response_format
      };
      
      if (isCloning) {
        // For cloning, create a new schema
        await docRouterOrgApi.createSchema(schemaConfig);
      } else {
        // For renaming, update existing schema
        await docRouterOrgApi.updateSchema({
          schemaId: selectedSchema.schema_id,
          schema: schemaConfig
        });
      }
      
      // Refresh the schema list
      await loadSchemas();
    } catch (error) {
      console.error(`Error ${isCloning ? 'cloning' : 'renaming'} schema:`, error);
      toast.error(`Failed to ${isCloning ? 'clone' : 'rename'} schema`);
      throw error;
    }
  };

  const handleCloseNameModal = () => {
    setIsNameModalOpen(false);
    setSelectedSchema(null);
    setIsCloning(false);
  };

  // Add a function to handle schema download
  const handleDownload = (schema: Schema) => {
    try {
      // Create a JSON blob from the schema
      const schemaJson = JSON.stringify(schema.response_format.json_schema, null, 2);
      const blob = new Blob([schemaJson], { type: 'application/json' });
      
      // Create a URL for the blob
      const url = URL.createObjectURL(blob);
      
      // Create a temporary anchor element to trigger the download
      const a = document.createElement('a');
      a.href = url;
      a.download = `${schema.name.replace(/\s+/g, '_')}_schema.json`;
      
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
      console.error('Error downloading schema:', error);
      setMessage('Error: Failed to download schema');
    }
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, schema: Schema) => {
    setAnchorEl(event.currentTarget);
    setSelectedSchema(schema);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  // Add a new function to handle clone operation
  const handleCloneOperation = (schema: Schema) => {
    setSelectedSchema(schema);
    setIsCloning(true);
    setIsNameModalOpen(true);
    handleMenuClose();
  };

  // Server-side filtering; no client-side filter
  const filteredSchemas = schemas;

  // Helper function to convert JSON schema to fields for display
  const jsonSchemaToFields = (responseFormat: SchemaResponseFormat): SchemaField[] => {
    const fields: SchemaField[] = [];
    const properties = responseFormat.json_schema.schema.properties;

    const processProperty = (name: string, prop: SchemaProperty): SchemaField => {
      let fieldType: SchemaField['type'];

      switch (prop.type) {
        case 'string':
          fieldType = 'str';
          break;
        case 'integer':
          fieldType = 'int';
          break;
        case 'number':
          fieldType = 'float';
          break;
        case 'boolean':
          fieldType = 'bool';
          break;
        case 'array':
          fieldType = 'array';
          break;
        case 'object':
          fieldType = 'object';
          break;
        default:
          fieldType = 'str';
      }

      return { 
        name, 
        type: fieldType,
        description: prop.description
      };
    };

    Object.entries(properties).forEach(([name, prop]) => {
      fields.push(processProperty(name, prop));
    });

    return fields;
  };

  // Define columns for the data grid
  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Schema Name',
      flex: 1,
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
      field: 'fields',
      headerName: 'Fields',
      flex: 2,
      headerAlign: 'left',
      align: 'left',
      renderCell: (params) => {
        // Convert JSON Schema to fields for display
        const fields = jsonSchemaToFields(params.row.response_format);
        return (
          <div className="flex flex-col justify-center w-full h-full">
            {fields.map((field, index) => (
              <div key={index} className="text-sm text-gray-600 leading-6">
                {`${field.name}: ${field.type}`}
              </div>
            ))}
          </div>
        );
      },
    },
    {
      field: 'schema_version',
      headerName: 'Version',
      width: 150,
      headerAlign: 'left',
      align: 'left',
      renderCell: (params) => (
        <div className="flex items-center gap-2">
          <span className="text-gray-600">v{params.row.schema_version}</span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setSelectedSchema(params.row);
              setIsInfoModalOpen(true);
            }}
            className="p-1 text-blue-600 hover:bg-blue-50 rounded-full transition-colors"
            title="View schema information"
          >
            <InfoIcon className="text-base" />
          </button>
        </div>
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      headerAlign: 'center',
      align: 'center',
      sortable: false,
      renderCell: (params) => (
        <div>
          <button
            onClick={(e) => handleMenuOpen(e, params.row)}
            disabled={isLoading}
            className="p-1.5 text-gray-600 hover:bg-gray-50 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <MoreVertIcon className="text-base" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="p-4 mx-auto">
      <div className="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-200 text-blue-800 hidden md:block">
        <p className="text-sm">
          Schemas define the structure for extracting key data fields from your documents. Below is a list of your existing schemas. 
          If none are available, <Link href={`/orgs/${organizationId}/schemas?tab=schema-create`} className="text-blue-600 font-medium hover:underline">click here</Link> or use the tab above to create a new schema.
        </p>
      </div>
      <h2 className="text-xl font-bold mb-4 hidden md:block">Schemas</h2>
      
      {/* Search Box */}
      <div className="mb-4">
        <TextField
          fullWidth
          variant="outlined"
          placeholder="Search schemas..."
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
          rows={filteredSchemas}
          columns={columns}
          getRowId={(row) => row.schema_revid}
          initialState={{
            pagination: {
              paginationModel: { pageSize: 5 }
            },
            sorting: {
              sortModel: [{ field: 'schema_revid', sort: 'desc' }]
            }
          }}
          pageSizeOptions={[5, 10, 20]}
          disableRowSelectionOnClick
          loading={isLoading}
          paginationMode="server"
          rowCount={total}
          onPaginationModelChange={(model) => {
            setPage(model.page);
            setPageSize(model.pageSize);
          }}
          getRowHeight={({ model }) => {
            const fields = jsonSchemaToFields(model.response_format);
            const numFields = fields.length;
            return Math.max(52, 24 * numFields + 16);
          }}
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
            if (selectedSchema) handleNameSchema(selectedSchema);
          }}
          className="flex items-center gap-2"
        >
          <DriveFileRenameOutlineIcon fontSize="small" className="text-indigo-800" />
          <span>Rename</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedSchema) handleCloneOperation(selectedSchema);
          }}
          className="flex items-center gap-2"
        >
          <ContentCopyIcon fontSize="small" className="text-purple-600" />
          <span>Clone</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedSchema) handleEdit(selectedSchema);
          }}
          className="flex items-center gap-2"
        >
          <EditOutlinedIcon fontSize="small" className="text-blue-600" />
          <span>Edit</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedSchema) handleDownload(selectedSchema);
          }}
          className="flex items-center gap-2"
        >
          <DownloadIcon fontSize="small" className="text-green-600" />
          <span>Download</span>
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedSchema) handleDelete(selectedSchema.schema_id);
          }}
          className="flex items-center gap-2"
        >
          <DeleteOutlineIcon fontSize="small" className="text-red-600" />
          <span>Delete</span>
        </MenuItem>
      </Menu>
      
      {/* Rename/Clone Modal */}
      {selectedSchema && (
        <SchemaNameModal
          isOpen={isNameModalOpen}
          onClose={handleCloseNameModal}
          schemaName={isCloning ? `${selectedSchema.name} (Copy)` : selectedSchema.name}
          onSubmit={handleNameSubmit}
          isCloning={isCloning}
          organizationId={organizationId}
        />
      )}
      
      {/* Info Modal */}
      {selectedSchema && (
        <SchemaInfoModal
          isOpen={isInfoModalOpen}
          onClose={() => {
            setIsInfoModalOpen(false);
            setSelectedSchema(null);
          }}
          schema={selectedSchema}
        />
      )}
    </div>
  );
};

export default SchemaList;