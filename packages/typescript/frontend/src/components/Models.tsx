import React, { useState } from 'react';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { TextField, InputAdornment } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { designTokens } from '@/lib/designTokens';

const Models: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const isLoading = false;

  // Temporary mock data - replace with actual data later
  const mockData = [
    { id: 1, name: 'Model 1', description: 'Description 1', status: 'Active' },
    { id: 2, name: 'Model 2', description: 'Description 2', status: 'Inactive' },
  ];

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Model Name',
      flex: 1,
      headerAlign: 'left',
      align: 'left',
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      headerAlign: 'left',
      align: 'left',
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      headerAlign: 'left',
      align: 'left',
    },
  ];

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-xl font-bold mb-4">Models (under construction)</h2>
      
      {/* Search Box */}
      <div className="mb-4">
        <TextField
          fullWidth
          variant="outlined"
          placeholder="Search models..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              )
            }
          }}
        />
      </div>

      {/* Data Grid */}
      <div style={{ height: 400, width: '100%' }}>
        <DataGrid
          rows={mockData}
          columns={columns}
          initialState={{
            pagination: {
              paginationModel: { pageSize: 5 }
            },
          }}
          pageSizeOptions={[5, 10, 20]}
          disableRowSelectionOnClick
          loading={isLoading}
          sx={{
            '& .MuiDataGrid-cell': {
              padding: '8px',
            },
            '& .MuiDataGrid-row:nth-of-type(odd)': {
              backgroundColor: designTokens.secondary,
            },
            '& .MuiDataGrid-row:hover': {
              backgroundColor: `${designTokens.border} !important`,
            },
          }}
        />
      </div>
    </div>
  );
};

export default Models;
