'use client'

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { IconButton } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { DocRouterAccountApi } from '@/utils/api';
import { User, UserCreate } from '@docrouter/sdk';
import { isAxiosError } from 'axios';
import colors from 'tailwindcss/colors';
import { useRouter } from 'next/navigation';
import { signOut } from 'next-auth/react';
import { useAppSession } from '@/utils/useAppSession';
import UserInviteModal from './UserInviteModal';
import UserAddModal from './UserAddModal';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';

interface DeleteUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
  onConfirm: () => Promise<void>;
}

const DeleteUserModal: React.FC<DeleteUserModalProps> = ({ isOpen, onClose, user, onConfirm }) => {
  if (!isOpen || !user) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
      <div className="bg-white p-6 rounded-lg shadow-xl max-w-md w-full">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Delete User</h3>
        <p className="text-gray-600 mb-6">
          Are you sure you want to delete user &quot;{user.email}&quot;? This action cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
          >
            Delete User
          </button>
        </div>
      </div>
    </div>
  );
};

const UserManager: React.FC = () => {
  const router = useRouter();
  const session = useAppSession();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [paginationModel, setPaginationModel] = useState({
    pageSize: 10,
    page: 0,
  });
  const [searchQuery, setSearchQuery] = useState('');
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  const fetchUsers = useCallback(async () => {
    try {
      const response = await docRouterAccountApi.listUsers({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        search_name: debouncedSearch || undefined
      });
      setUsers(response.users);
      setTotalCount(response.total_count);
    } catch (error) {
      if (isAxiosError(error)) {
        console.error('Error fetching users:', error.response?.data);
      }
    } finally {
      setLoading(false);
    }
  }, [paginationModel, debouncedSearch, docRouterAccountApi]);

  useEffect(() => {
    fetchUsers();
  }, [paginationModel, fetchUsers]);

  // Debounce search input
  useEffect(() => {
    const handle = setTimeout(() => setDebouncedSearch(searchQuery.trim()), 300);
    return () => clearTimeout(handle);
  }, [searchQuery]);

  const handleDeleteClick = (userId: string) => {
    const user = users.find(u => u.id === userId);
    if (user) {
      setUserToDelete(user);
      setIsDeleteModalOpen(true);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!userToDelete) return;

    try {
      await docRouterAccountApi.deleteUser(userToDelete.id);
      
      if (session?.session?.user?.id === userToDelete.id) {
        signOut({ callbackUrl: '/auth/signin' });
        return;
      }
      
      fetchUsers();
      setIsDeleteModalOpen(false);
      setUserToDelete(null);
    } catch (error) {
      if (isAxiosError(error)) {
        const errorMessage = error.response?.data?.detail || 'Failed to delete user';
        alert(errorMessage);
      }
    }
  };

  // Server-side filtering; rows are the fetched users
  const filteredUsers = users;

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, user: User) => {
    setAnchorEl(event.currentTarget);
    setSelectedUser(user);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedUser(null);
  };

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'User',
      flex: 1,
      minWidth: 300,
      renderCell: (params: GridRenderCellParams) => (
        <button
          onClick={() => router.push(`/settings/account/users/${params.row.id}`)}
          className="text-left hover:text-blue-600 focus:outline-none"
        >
          <span className="font-medium">{params.value || 'Unnamed User'}</span>
          <span className="text-gray-500 ml-2">({params.row.email})</span>
        </button>
      )
    },
    { 
      field: 'role', 
      headerName: 'Role', 
      width: 120,
      renderCell: (params) => (
        <span className={params.value === 'admin' ? 'text-blue-600' : ''}>
          {params.value}
        </span>
      )
    },
    {
      field: 'email_verified',
      headerName: 'Email Verified',
      width: 130,
      renderCell: (params) => (
        <span className={params.value ? 'text-green-600' : 'text-gray-500'}>
          {params.value ? 'Yes' : 'No'}
        </span>
      )
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 80,
      renderCell: (params) => (
        <div>
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

  // Calculate the current range for status text
  const startRange = (paginationModel.page * paginationModel.pageSize) + 1;

  const handleAddUser = async (userData: UserCreate) => {
    try {
      await docRouterAccountApi.createUser(userData);
      await fetchUsers();
    } catch (error) {
      throw error; // Let the modal handle the error
    }
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold text-gray-900">User Management</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            Add User
          </button>
          <button
            onClick={() => setIsInviteModalOpen(true)}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
          >
            Invite User
          </button>
        </div>
      </div>

      {/* Search Box */}
      <div className="mb-4">
        <input
          type="text"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          placeholder="Search users by name or email..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <div style={{ height: 400, width: '100%' }}>
        <DataGrid
          rows={filteredUsers}
          columns={columns}
          loading={loading}
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          pageSizeOptions={[10, 25, 50]}
          paginationMode="server"
          rowCount={totalCount}
          disableRowSelectionOnClick
          getRowId={(row) => row.id}
          sx={{
            '& .MuiDataGrid-cell': {
              padding: 'px',
            },
            '& .MuiDataGrid-row:nth-of-type(odd)': {
              backgroundColor: colors.gray[100],
            },
            '& .MuiDataGrid-row:hover': {
              backgroundColor: `${colors.gray[200]} !important`,
            }
          }}
        />
      </div>

      <div className="mt-4 text-sm text-gray-600">
        {loading ? 'Loading...' :
          users.length > 0 ?
            `Showing ${startRange}-${startRange + users.length - 1} of ${totalCount} users` :
            'No users found'
        }
      </div>

      <DeleteUserModal
        isOpen={isDeleteModalOpen}
        onClose={() => {
          setIsDeleteModalOpen(false);
          setUserToDelete(null);
        }}
        user={userToDelete}
        onConfirm={handleDeleteConfirm}
      />

      <UserAddModal
        open={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onAdd={handleAddUser}
      />

      <UserInviteModal
        open={isInviteModalOpen}
        onClose={() => setIsInviteModalOpen(false)}
        onInvited={fetchUsers}
      />

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem
          onClick={() => {
            if (selectedUser) router.push(`/settings/account/users/${selectedUser.id}`);
            handleMenuClose();
          }}
          className="flex items-center gap-2"
        >
          <EditIcon fontSize="small" className="text-blue-600" />
          <span>Edit</span>
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedUser) handleDeleteClick(selectedUser.id);
            handleMenuClose();
          }}
          className="flex items-center gap-2"
        >
          <DeleteIcon fontSize="small" className="text-red-600" />
          <span>Delete</span>
        </MenuItem>
      </Menu>
    </div>
  );
};

export default UserManager; 