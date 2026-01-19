'use client'

import React, { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { OrganizationMember, OrganizationType } from '@/types/index'
import { DocRouterAccountApi } from '@/utils/api'
import { isAxiosError } from 'axios'
import { User } from '@docrouter/sdk'
import { 
  DataGrid, 
  GridColDef, 
  GridRenderCellParams 
} from '@mui/x-data-grid'
import { Switch, IconButton } from '@mui/material'
import DeleteIcon from '@mui/icons-material/Delete'
import { useAppSession } from '@/contexts/AppSessionContext'
import UserAddToOrgModal from './UserAddToOrgModal'
import { toast } from 'react-toastify'
import MoreVertIcon from '@mui/icons-material/MoreVert';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import { useOrganizationData } from '@/hooks/useOrganizationData'
import { isSysAdmin, isOrgAdmin } from '@/utils/roles'

interface OrganizationEditProps {
  organizationId: string
}

const getAvailableOrganizationTypes = (currentType: OrganizationType, isSystemAdmin: boolean): OrganizationType[] => {
  switch (currentType) {
    case 'individual':
      // Only system admins can upgrade to enterprise
      if (isSystemAdmin) {
        return ['individual', 'team', 'enterprise'];
      }
      return ['individual', 'team'];
    case 'team':
      // Only system admins can upgrade to enterprise
      if (isSystemAdmin) {
        return ['team', 'enterprise'];
      }
      return ['team'];
    case 'enterprise':
      return ['enterprise'];
    default:
      if (isSystemAdmin) {
        return ['individual', 'team', 'enterprise'];
      }
      return ['individual', 'team'];
  }
};

const OrganizationEdit: React.FC<OrganizationEditProps> = ({ organizationId }) => {
  const router = useRouter()
  const { organization, loading, refreshData } = useOrganizationData(organizationId)
  const [name, setName] = useState('')
  const [type, setType] = useState<OrganizationType>('individual')
  const [members, setMembers] = useState<OrganizationMember[]>([])
  const [allUsers, setAllUsers] = useState<User[]>([])
  const [memberSearch, setMemberSearch] = useState('');
  const [originalName, setOriginalName] = useState('')
  const [originalType, setOriginalType] = useState<OrganizationType>('individual')
  const [originalMembers, setOriginalMembers] = useState<OrganizationMember[]>([])
  const { session } = useAppSession();
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedMember, setSelectedMember] = useState<{ id: string, isAdmin: boolean } | null>(null);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);

  // Filter current organization members
  const filteredMembers = members.filter(member => {
    const user = allUsers.find(u => u.id === member.user_id);
    return user && (
      user.name?.toLowerCase().includes(memberSearch.toLowerCase()) || 
      user.email.toLowerCase().includes(memberSearch.toLowerCase())
    );
  });

  // Update local state when organization data changes
  useEffect(() => {
    if (organization) {
      setName(organization.name);
      setType(organization.type);
      setMembers(organization.members);

      // Store original values
      setOriginalName(organization.name);
      setOriginalType(organization.type);
      setOriginalMembers(organization.members);
    }
  }, [organization]);

  // Separate useEffect for fetching users
  useEffect(() => {
    const fetchUsers = async () => {
      const isUserOrgAdmin = organization ? isOrgAdmin(organization, session) : false;
      const isUserSysAdmin = isSysAdmin(session);
      
      if (isUserOrgAdmin || isUserSysAdmin) {
        let allUsers: User[] = [];
        let skip = 0;
        const limit = 100;
        let total = 0;

        do {
          const usersResponse = await docRouterAccountApi.listUsers({ organization_id: organizationId, skip, limit });
          allUsers = allUsers.concat(usersResponse.users);
          total = usersResponse.total_count;
          skip += limit;
        } while (allUsers.length < total);

        setAllUsers(allUsers);
      }
    };

    fetchUsers();
  }, [organizationId, organization, session, docRouterAccountApi]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateAdminPresence(members)) {
      toast.error('Organization must have at least one admin');
      return;
    }

    // Validate individual organization member count
    if (type === 'individual' && members.length > 1) {
      toast.error('Individual organizations cannot have multiple members');
      return;
    }

    // Check if user is trying to upgrade to Enterprise without admin privileges
    if ((originalType === 'individual' || originalType === 'team') && type === 'enterprise' && !isSysAdmin(session)) {
      toast.error('Only system administrators can upgrade organizations to Enterprise');
      return;
    }

    try {
      await docRouterAccountApi.updateOrganization(organizationId, { 
        name,
        type,
        members 
      });
      await refreshData();
      
      // Update original values after successful save
      setOriginalName(name);
      setOriginalType(type);
      setOriginalMembers(members);
    } catch (err) {
      if (isAxiosError(err)) {
        toast.error(err.response?.data?.detail || 'Failed to update organization');
      } else {
        toast.error('An unexpected error occurred');
      }
    }
  };

  const handleRoleChange = (userId: string, newRole: 'admin' | 'user') => {
    setMembers(prevMembers => {
      const updatedMembers = prevMembers.map(member => 
        member.user_id === userId ? { ...member, role: newRole } : member
      );
      
      // If the change would result in no admins, prevent it
      if (!validateAdminPresence(updatedMembers)) {
        toast.error('Organization must have at least one admin');
        return prevMembers; // Keep the original state
      }

      return updatedMembers;
    });
  };

  const handleAddMember = async (userId: string): Promise<void> => {
    // Prevent adding members to individual organizations
    if (type === 'individual') {
      toast.error('Individual organizations cannot have multiple members');
      return;
    }

    if (!members.some(member => member.user_id === userId)) {
      setMembers(prev => [...prev, { user_id: userId, role: 'user' }]);
    }
  };

  const handleRemoveMember = (userId: string) => {
    const memberToRemove = members.find(member => member.user_id === userId);
    if (memberToRemove?.role === 'admin') {
      // Check if this is the last admin
      const remainingAdmins = members.filter(m => m.role === 'admin' && m.user_id !== userId);
      if (remainingAdmins.length === 0) {
        toast.error('Cannot remove the last admin. Promote another member to admin first.');
        return;
      }
    }
    
    setMembers(prev => prev.filter(member => member.user_id !== userId));
  };

  // Update getGridRows to use filtered members
  const getGridRows = () => {
    return filteredMembers.map(member => {
      const user = allUsers.find(u => u.id === member.user_id)
      return {
        id: member.user_id,
        name: user?.name || 'Unknown User',
        email: user?.email || '',
        isAdmin: member.role === 'admin'
      }
    })
  }

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, memberId: string, isAdmin: boolean) => {
    setAnchorEl(event.currentTarget);
    setSelectedMember({ id: memberId, isAdmin });
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedMember(null);
  };

  // Define columns for the grid
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
          <span className="font-medium">{params.value}</span>
          <span className="text-gray-500 ml-2">({params.row.email})</span>
        </button>
      )
    },
    {
      field: 'isAdmin',
      headerName: 'Admin',
      width: 120,
      renderCell: (params: GridRenderCellParams) => (
        <span className={params.value ? 'text-blue-600' : ''}>
          {params.value ? 'Admin' : 'User'}
        </span>
      )
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 80,
      renderCell: (params: GridRenderCellParams) => (
        <div>
          <IconButton
            onClick={(e) => handleMenuOpen(e, params.row.id, params.row.isAdmin)}
            className="text-gray-600 hover:bg-gray-50"
          >
            <MoreVertIcon />
          </IconButton>
        </div>
      )
    }
  ]

  // Check if form has changes
  const hasChanges = () => {
    if (name !== originalName) return true;
    if (type !== originalType) return true;
    if (members.length !== originalMembers.length) return true;
    
    // Compare each member and their roles
    const memberChanges = members.some(member => {
      const originalMember = originalMembers.find(m => m.user_id === member.user_id);
      return !originalMember || originalMember.role !== member.role;
    });
    
    return memberChanges;
  };

  // Add this validation function after the hasChanges function
  const validateAdminPresence = (updatedMembers: OrganizationMember[]): boolean => {
    return updatedMembers.some(member => member.role === 'admin');
  };

  // Replace the permission check block with this:
  if (!loading) {
    const isUserOrgAdmin = organization ? isOrgAdmin(organization, session) : false;
    const isUserSysAdmin = isSysAdmin(session);
    
    if (!isUserOrgAdmin && !isUserSysAdmin) {
      return (
        <div className="flex items-center justify-center p-4">
          You don&apos;t have permission to edit this organization. Only organization admins and system admins can edit organizations.
        </div>
      );
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        Loading...
      </div>
    );
  }

  if (!organization) {
    return <div className="flex items-center justify-center p-4">Organization not found</div>
  }

  return (
    <div className="max-w-4xl mx-auto bg-white rounded-lg shadow p-6 min-h-[calc(100vh-80px)] flex flex-col">
      <div className="flex flex-col flex-1 h-0">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-semibold">Edit Organization</h2>
          <div className="flex gap-4">
            {/* Subscription Link - Only show for org admins and sys admins */}
            {(() => {
              const isUserOrgAdmin = organization ? isOrgAdmin(organization, session) : false;
              const isUserSysAdmin = isSysAdmin(session);
              return (isUserOrgAdmin || isUserSysAdmin) ? (
                <>
                  <a
                    href={`/settings/organizations/${organizationId}/subscription`}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                    </svg>
                    Billing
                  </a>
                </>
              ) : null;
            })()}
            <button
              type="submit"
              form="organization-form"
              disabled={!hasChanges()}
              className={`px-4 py-2 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                ${hasChanges() 
                  ? 'bg-blue-600 text-white hover:bg-blue-700' 
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'}`}
            >
              Save Changes
            </button>
            <button
              type="button"
              onClick={() => router.push('/settings/organizations')}
              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              Cancel
            </button>
          </div>
        </div>
        
        <form id="organization-form" onSubmit={handleSubmit} className="flex flex-col flex-1">
          {/* Organization Name Section */}
          <div className="bg-gray-50 p-4 rounded-lg mb-6">
            <div className="space-y-4">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                  Organization Name
                </label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                />
              </div>
              
              <div>
                <label htmlFor="type" className="block text-sm font-medium text-gray-700 mb-1">
                  Organization Type
                </label>
                <select
                  id="type"
                  name="type"
                  value={type}
                  onChange={(e) => setType(e.target.value as OrganizationType)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white disabled:bg-gray-100 disabled:cursor-not-allowed"
                >
                  {getAvailableOrganizationTypes(originalType, isSysAdmin(session)).map((orgType) => (
                    <option key={orgType} value={orgType}>
                      {orgType.charAt(0).toUpperCase() + orgType.slice(1)}
                    </option>
                  ))}
                  {/* Show Enterprise option as disabled for non-admin users */}
                  {!isSysAdmin(session) && (originalType === 'individual' || originalType === 'team') && (
                    <option value="enterprise" disabled>
                      Enterprise (Admin Only)
                    </option>
                  )}
                </select>
              </div>
            </div>
          </div>

          {/* Members Section - adjust the height calculation */}
          <div className="flex-1 bg-gray-50 p-4 rounded-lg flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium text-gray-900">Members</h3>
              
              <button
                type="button"
                onClick={() => setShowAddUserModal(true)}
                disabled={type === 'individual'}
                className={`px-4 py-2 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                  ${type === 'individual' 
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                    : 'bg-blue-600 text-white hover:bg-blue-700'}`}
              >
                Add User
              </button>
            </div>

            <div className="mb-4">
              <input
                type="text"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                placeholder="Search members..."
                value={memberSearch}
                onChange={(e) => setMemberSearch(e.target.value)}
              />
            </div>

            {/* Update the DataGrid container height */}
            <div className="flex-1 bg-white rounded-lg flex flex-col">
              <DataGrid
                rows={getGridRows()}
                columns={columns}
                initialState={{
                  pagination: {
                    paginationModel: { pageSize: 5 }
                  }
                }}
                pageSizeOptions={[5, 10, 20]}
                disableRowSelectionOnClick
                disableColumnMenu
                density="standard"
                sx={{
                  flex: 1,
                  minHeight: 100,
                  height: '100%',
                  '& .MuiDataGrid-row': {
                    height: '60px'
                  },
                  '& .MuiDataGrid-row:nth-of-type(odd)': {
                    backgroundColor: '#f9fafb'
                  },
                  '& .MuiDataGrid-cell': {
                    height: '60px',
                    alignItems: 'center',
                    padding: '0 16px'
                  }
                }}
              />
              {/* Actions Menu for member row */}
              <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleMenuClose}
              >
                <MenuItem
                  onClick={() => {
                    if (selectedMember) {
                      handleRoleChange(
                        selectedMember.id,
                        selectedMember.isAdmin ? 'user' : 'admin'
                      );
                    }
                    handleMenuClose();
                  }}
                  className="flex items-center gap-2"
                  disabled={!selectedMember}
                >
                  <Switch
                    checked={selectedMember?.isAdmin || false}
                    onChange={() => {
                      if (selectedMember) {
                        handleRoleChange(
                          selectedMember.id,
                          selectedMember.isAdmin ? 'user' : 'admin'
                        );
                      }
                      handleMenuClose();
                    }}
                    color="primary"
                    size="small"
                    inputProps={{ 'aria-label': 'Toggle admin' }}
                  />
                  <span>
                    {selectedMember?.isAdmin ? 'Remove Admin' : 'Make Admin'}
                  </span>
                </MenuItem>
                <MenuItem
                  onClick={() => {
                    if (selectedMember) handleRemoveMember(selectedMember.id);
                    handleMenuClose();
                  }}
                  className="flex items-center gap-2"
                  disabled={!selectedMember}
                >
                  <DeleteIcon fontSize="small" className="text-red-600" />
                  <span>Remove</span>
                </MenuItem>
              </Menu>
            </div>
          </div>
        </form>
      </div>

      <UserAddToOrgModal
        open={showAddUserModal}
        onClose={() => setShowAddUserModal(false)}
        onAdd={handleAddMember}
        organizationId={organizationId}
        currentMembers={members.map(member => member.user_id)}
      />
    </div>
  )
}

export default OrganizationEdit 