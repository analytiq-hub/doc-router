'use client'

import React, { useState, useEffect } from 'react';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { IconButton } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { getAllWorkspacesApi, isAxiosError } from '@/utils/api';
import { Workspace } from '@/app/types/Api';
import colors from 'tailwindcss/colors';

const WorkspaceManager: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchWorkspaces = async () => {
    try {
      const response = await getAllWorkspacesApi();
      setWorkspaces(response.workspaces);
    } catch (error) {
      if (isAxiosError(error)) {
        console.error('Error fetching workspaces:', error.response?.data);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const columns: GridColDef[] = [
    { field: 'name', headerName: 'Name', flex: 1 },
    { 
      field: 'members', 
      headerName: 'Members', 
      flex: 1,
      renderCell: (params) => (
        <span>{params.value.length} members</span>
      )
    },
    { 
      field: 'created_at', 
      headerName: 'Created', 
      flex: 1,
      renderCell: (params) => (
        <span>{new Date(params.value).toLocaleDateString()}</span>
      )
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      renderCell: () => (
        <div className="flex gap-2">
          <IconButton
            onClick={() => {/* TODO: Implement edit */}}
            className="text-blue-600 hover:bg-blue-50"
          >
            <EditIcon />
          </IconButton>
          <IconButton
            onClick={() => {/* TODO: Implement delete */}}
            className="text-red-600 hover:bg-red-50"
          >
            <DeleteIcon />
          </IconButton>
        </div>
      ),
    },
  ];

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <div style={{ height: 400, width: '100%' }}>
        <DataGrid
          rows={workspaces}
          columns={columns}
          loading={loading}
          pageSizeOptions={[10, 25, 50]}
          disableRowSelectionOnClick
          getRowId={(row) => row.id}
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

      {/* Status Text */}
      <div className="mt-4 text-sm text-gray-600">
        {loading ? 'Loading...' : 
          workspaces.length > 0 ? 
            `Showing ${workspaces.length} workspaces` : 
            'No workspaces found'
        }
      </div>
    </div>
  );
};

export default WorkspaceManager; 