'use client'

import React, { useState, useEffect } from 'react';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { IconButton, Dialog, DialogTitle, DialogContent, DialogActions, Button } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { getOrganizationsApi, deleteOrganizationApi, createOrganizationApi } from '@/utils/api';
import { Organization, CreateOrganizationRequest } from '@/types/index';
import colors from 'tailwindcss/colors';
import { isAxiosError } from 'axios';
import { useRouter } from 'next/navigation'
import { useOrganization } from '@/contexts/OrganizationContext';

interface AddOrganizationModalProps {
  open: boolean;
  onClose: () => void;
  onAdd: (organization: CreateOrganizationRequest) => Promise<void>;
}

const AddOrganizationModal: React.FC<AddOrganizationModalProps> = ({ open, onClose, onAdd }) => {
  const [name, setName] = useState('');
  const [type, setType] = useState<'team' | 'enterprise'>('team');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      setName('');
      setType('team');
      setError(null);
      setLoading(false);
    }
  }, [open]);

  const handleClose = () => {
    setError(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await onAdd({ name, type });
      setName('');
      handleClose();
    } catch (error) {
      if (isAxiosError(error)) {
        setError(error.response?.data?.detail || 'Failed to create organization');
      } else if (error instanceof Error) {
        setError(error.message);
      } else {
        setError('An unexpected error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Create New Organization</DialogTitle>
        <DialogContent>
          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative">
              <span className="block sm:inline">{error}</span>
            </div>
          )}
          <div className="mt-4 space-y-4">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                Organization Name
              </label>
              <input
                type="text"
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                placeholder="Enter organization name"
                required
                autoFocus
              />
            </div>
            <div>
              <label htmlFor="type" className="block text-sm font-medium text-gray-700 mb-1">
                Organization Type
              </label>
              <select
                id="type"
                value={type}
                onChange={(e) => setType(e.target.value as 'team' | 'enterprise')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="team">Team</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
          </div>
        </DialogContent>
        <DialogActions className="p-4">
          <Button onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={loading || !name.trim()}
          >
            Create
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

const OrganizationManager: React.FC = () => {
  const router = useRouter()
  const { refreshOrganizations } = useOrganization();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteOrganizationId, setDeleteOrganizationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchOrganizations = async () => {
    try {
      const response = await getOrganizationsApi();
      setOrganizations(response.organizations);
    } catch (error) {
      if (isAxiosError(error)) {
        console.error('Error fetching organizations:', error.response?.data);
      }
    } finally {
      setLoading(false);
    }
  };

  const filteredOrganizations = organizations.filter(org =>
    org.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  useEffect(() => {
    fetchOrganizations();
  }, []);

  const handleDeleteClick = (organizationId: string) => {
    setDeleteOrganizationId(organizationId);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteOrganizationId) return;

    try {
      await deleteOrganizationApi(deleteOrganizationId);
      setOrganizations(prevOrganizations => 
        prevOrganizations.filter(o => o.id !== deleteOrganizationId)
      );
      setDeleteOrganizationId(null);
      await refreshOrganizations();
    } catch (error) {
      if (isAxiosError(error)) {
        setError(error.response?.data?.detail || 'Failed to delete organization');
      } else {
        setError('An unexpected error occurred');
      }
    }
  };

  const handleAddOrganization = async (organization: CreateOrganizationRequest) => {
    try {
      // Check for duplicate names (case-insensitive)
      const isDuplicate = organizations.some(
        org => org.name.toLowerCase() === organization.name.toLowerCase()
      );
      
      if (isDuplicate) {
        throw new Error(`An organization named "${organization.name}" already exists`);
      }

      await createOrganizationApi(organization);
      await fetchOrganizations();
      await refreshOrganizations();
    } catch (error) {
      throw error;
    }
  };

  const columns: GridColDef[] = [
    { 
      field: 'name', 
      headerName: 'Name', 
      flex: 1,
      renderCell: (params) => (
        <button
          onClick={() => router.push(`/settings/organizations/${params.row.id}`)}
          className="text-left hover:text-blue-600 focus:outline-none"
        >
          {params.value}
        </button>
      )
    },
    {
      field: 'type',
      headerName: 'Type',
      flex: 1,
      renderCell: (params) => {
        const typeColors = {
          team: 'bg-blue-100 text-blue-800',
          enterprise: 'bg-purple-100 text-purple-800'
        };
        
        return (
          <span className={`px-2 py-1 rounded-full text-sm ${typeColors[params.value as keyof typeof typeColors]}`}>
            {params.value.charAt(0).toUpperCase() + params.value.slice(1)}
          </span>
        );
      }
    },
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
      renderCell: (params) => (
        <div className="flex gap-2 items-center h-full">
          <IconButton
            onClick={() => router.push(`/settings/organizations/${params.row.id}`)}
            className="text-blue-600 hover:bg-blue-50"
          >
            <EditIcon />
          </IconButton>
          <IconButton
            onClick={() => handleDeleteClick(params.row.id)}
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
      {error && (
        <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-md">
          {error}
        </div>
      )}

      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold">Organizations</h2>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          Add Organization
        </button>
      </div>

      <div className="mb-4">
        <div className="relative">
          <input
            type="text"
            placeholder="Search organizations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white pl-10"
          />
          <svg
            className="absolute left-3 top-2.5 h-5 w-5 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>
      </div>

      <div style={{ height: 400, width: '100%' }}>
        <DataGrid
          rows={filteredOrganizations}
          columns={columns}
          loading={loading}
          pageSizeOptions={[10, 25, 50]}
          disableRowSelectionOnClick
          getRowId={(row) => row.id}
          sx={{
            '& .MuiDataGrid-cell': {
              padding: 'px'
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
          organizations.length > 0 ? 
            `Showing ${filteredOrganizations.length} of ${organizations.length} organizations` : 
            'No organizations found'
        }
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={Boolean(deleteOrganizationId)}
        onClose={() => setDeleteOrganizationId(null)}
      >
        <DialogTitle>Delete Organization</DialogTitle>
        <DialogContent>
          <p className="mt-2">
            Are you sure you want to delete this organization? This action cannot be undone.
          </p>
        </DialogContent>
        <DialogActions className="p-4">
          <Button
            onClick={() => setDeleteOrganizationId(null)}
            className="text-gray-600"
          >
            Cancel
          </Button>
          <Button
            onClick={handleDeleteConfirm}
            className="bg-red-600 text-white hover:bg-red-700"
            variant="contained"
            color="error"
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      <AddOrganizationModal
        open={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onAdd={handleAddOrganization}
      />
    </div>
  );
};

export default OrganizationManager; 