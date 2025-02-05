import React, { useState, useEffect, useCallback } from 'react';
import { createSchemaApi, listSchemasApi, deleteSchemaApi, updateSchemaApi } from '@/utils/api';
import { SchemaField, Schema, SchemaConfig } from '@/types/index';
import { getApiErrorMsg } from '@/utils/api';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { TextField, InputAdornment, IconButton } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import colors from 'tailwindcss/colors'


const Schemas = ({ organizationId }: { organizationId: string }) => {
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [currentSchemaId, setCurrentSchemaId] = useState<string | null>(null);
  const [currentSchema, setCurrentSchema] = useState<SchemaConfig>({
    name: '',
    fields: [{ name: '', type: 'str' }]
  });
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(5);
  const [total, setTotal] = useState(0);

  const saveSchema = async (schema: SchemaConfig) => {
    try {
      setIsLoading(true);
      
      if (currentSchemaId) {
        await updateSchemaApi({organizationId: organizationId, schemaId: currentSchemaId, schema});
      } else {
        await createSchemaApi({organizationId: organizationId, ...schema });
      }

      setPage(0);
      await loadSchemas();
      
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error saving schema';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const loadSchemas = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await listSchemasApi({
        organizationId: organizationId,
        skip: page * pageSize,
        limit: pageSize
      });
      setSchemas(response.schemas);
      setTotal(response.total_count);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading schemas';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, organizationId]);

  const handleDelete = async (schemaId: string) => {
    try {
      setIsLoading(true);
      await deleteSchemaApi({organizationId: organizationId, schemaId});
      setSchemas(schemas.filter(schema => schema.id !== schemaId));
      setMessage('Schema deleted successfully');
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error deleting schema';
      setMessage('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadSchemas();
  }, [loadSchemas]);

  const addField = () => {
    setCurrentSchema({
      ...currentSchema,
      fields: [...currentSchema.fields, { name: '', type: 'str' }]
    });
  };

  const removeField = (index: number) => {
    const newFields = currentSchema.fields.filter((_, i) => i !== index);
    setCurrentSchema({ ...currentSchema, fields: newFields });
  };

  const updateField = (index: number, field: Partial<SchemaField>) => {
    const newFields = currentSchema.fields.map((f, i) => 
      i === index ? { ...f, ...field } : f
    );
    setCurrentSchema({ ...currentSchema, fields: newFields });
  };

  const validateFields = (fields: SchemaField[]): string | null => {
    const fieldNames = fields.map(f => f.name.toLowerCase());
    const duplicates = fieldNames.filter((name, index) => fieldNames.indexOf(name) !== index);
    
    if (duplicates.length > 0) {
      return `Duplicate field name: ${duplicates[0]}`;
    }
    
    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentSchema.name || currentSchema.fields.some(f => !f.name)) {
      setMessage('Please fill in all fields');
      return;
    }

    const fieldError = validateFields(currentSchema.fields);
    if (fieldError) {
      setMessage(`Error: ${fieldError}`);
      return;
    }

    saveSchema(currentSchema);
    setCurrentSchema({ name: '', fields: [{ name: '', type: 'str' }] });
    setCurrentSchemaId(null);
  };

  // Add filtered schemas
  const filteredSchemas = schemas.filter(schema =>
    schema.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Define columns for the data grid
  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Schema Name',
      flex: 1,
      headerAlign: 'left',
      align: 'left',
      renderCell: (params) => (
        <div className="text-blue-600">
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
      renderCell: (params) => (
        <div className="flex flex-col justify-center w-full h-full">
          {params.row.fields.map((field: SchemaField, index: number) => (
            <div key={index} className="text-sm text-gray-600 leading-6">
              {`${field.name}: ${field.type}`}
            </div>
          ))}
        </div>
      ),
    },
    {
      field: 'version',
      headerName: 'Version',
      width: 100,
      headerAlign: 'left',
      align: 'left',
      renderCell: (params) => (
        <div className="text-gray-600">
          v{params.row.version}
        </div>
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      headerAlign: 'left',
      align: 'left',
      sortable: false,
      renderCell: (params) => (
        <div className="flex gap-2 items-center h-full">
          <IconButton
            onClick={() => {
              setCurrentSchemaId(params.row.id);
              setCurrentSchema({
                name: params.row.name,
                fields: params.row.fields
              });
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
            disabled={isLoading}
            className="text-blue-600 hover:bg-blue-50"
          >
            <EditOutlinedIcon />
          </IconButton>
          <IconButton
            onClick={() => handleDelete(params.row.id)}
            disabled={isLoading}
            className="text-red-600 hover:bg-red-50"
          >
            <DeleteOutlineIcon />
          </IconButton>
        </div>
      ),
    },
  ];

  return (
    <div className="p-4 max-w-4xl mx-auto">
      {/* Schema Creation Form */}
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <h2 className="text-xl font-bold mb-4">Create Schema</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="text"
              className="w-full p-2 border rounded"
              value={currentSchema.name}
              onChange={e => setCurrentSchema({ ...currentSchema, name: e.target.value })}
              placeholder="Schema Name"
              disabled={isLoading}
            />
          </div>

          {/* Fields */}
          <div className="space-y-3">
            {currentSchema.fields.map((field, index) => (
              <div key={index} className="flex gap-2">
                <input
                  type="text"
                  className="flex-1 p-2 border rounded"
                  value={field.name}
                  onChange={e => updateField(index, { name: e.target.value })}
                  placeholder="field_name"
                  disabled={isLoading}
                />
                <select
                  className="p-2 border rounded"
                  value={field.type}
                  onChange={e => updateField(index, { type: e.target.value as SchemaField['type'] })}
                  disabled={isLoading}
                >
                  <option value="str">String</option>
                  <option value="int">Integer</option>
                  <option value="float">Float</option>
                  <option value="bool">Boolean</option>
                  <option value="datetime">DateTime</option>
                </select>
                <button
                  type="button"
                  onClick={() => removeField(index)}
                  className="px-3 py-2 bg-red-50 text-red-600 rounded hover:bg-red-100 disabled:opacity-50"
                  disabled={isLoading}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>

          {/* Buttons */}
          <div className="flex gap-4">
            <button
              type="button"
              onClick={addField}
              className="px-4 py-2 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 disabled:opacity-50"
              disabled={isLoading}
            >
              Add Field
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              disabled={isLoading}
            >
              Save Schema
            </button>
          </div>
        </form>

        {/* Message */}
        {message && (
          <div className={`mt-4 p-3 rounded ${
            message.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'
          }`}>
            {message}
          </div>
        )}
      </div>

      {/* Schemas List */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">Schemas</h2>
        
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

        {/* Data Grid */}
        <div style={{ height: 400, width: '100%' }}>
          <DataGrid
            rows={filteredSchemas}
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
            paginationMode="server"
            rowCount={total}
            onPaginationModelChange={(model) => {
              setPage(model.page);
              setPageSize(model.pageSize);
            }}
            getRowHeight={({ model }) => {
              const numFields = model.fields.length;
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
      </div>
    </div>
  );
};

export default Schemas;