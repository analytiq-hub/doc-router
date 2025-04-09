'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Organization, OrganizationMember, OrganizationType } from '@/types/index'
import { updateOrganizationApi, getUsersApi, getOrganizationApi } from '@/utils/api'
import { isAxiosError } from 'axios'
import { useOrganization } from '@/contexts/OrganizationContext'
import { UserResponse } from '@/types/index'
import { 
  DataGrid, 
  GridColDef, 
  GridRenderCellParams 
} from '@mui/x-data-grid'
import { Switch, IconButton } from '@mui/material'
import DeleteIcon from '@mui/icons-material/Delete'
import { useSession } from 'next-auth/react'
import UserAddToOrgModal from './UserAddToOrgModal'
import { toast } from 'react-hot-toast'
import InfoTooltip from '@/components/InfoTooltip'

interface OrganizationEditProps {
  organizationId: string
}

const getAvailableOrganizationTypes = (currentType: OrganizationType): OrganizationType[] => {
  switch (currentType) {
    case 'individual':
      return ['individual', 'team', 'enterprise'];
    case 'team':
      return ['team', 'enterprise'];
    case 'enterprise':
      return ['enterprise'];
    default:
      return ['individual', 'team', 'enterprise'];
  }
};

const OrganizationEdit: React.FC<OrganizationEditProps> = ({ organizationId }) => {
  const router = useRouter()
  const { refreshOrganizations } = useOrganization()
  const [organization, setOrganization] = useState<Organization | null>(null)
  const [name, setName] = useState('')
  const [type, setType] = useState<OrganizationType>('individual')
  const [members, setMembers] = useState<OrganizationMember[]>([])
  const [allUsers, setAllUsers] = useState<UserResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [memberSearch, setMemberSearch] = useState('');
  const [originalName, setOriginalName] = useState('')
  const [originalType, setOriginalType] = useState<OrganizationType>('individual')
  const [originalMembers, setOriginalMembers] = useState<OrganizationMember[]>([])
  const { data: session } = useSession();
  const [isOrgAdmin, setIsOrgAdmin] = useState(false);
  const [isSysAdmin, setIsSysAdmin] = useState(false);
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [mcpEnabled, setMcpEnabled] = useState(false);
  const [originalMcpEnabled, setOriginalMcpEnabled] = useState(false);

  // Filter current organization members
  const filteredMembers = members.filter(member => {
    const user = allUsers.find(u => u.id === member.user_id);
    return user && (
      user.name?.toLowerCase().includes(memberSearch.toLowerCase()) || 
      user.email.toLowerCase().includes(memberSearch.toLowerCase())
    );
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const organization = await getOrganizationApi(organizationId);
        setOrganization(organization);
        setName(organization.name);
        setType(organization.type);
        setMembers(organization.members);
        setMcpEnabled(organization.mcp_enabled || false);

        // Check if current user is system admin or organization admin
        if (session?.user?.id) {
          const isSystemAdmin = session.user.role === 'admin';
          setIsSysAdmin(isSystemAdmin);

          const currentUserMember = organization.members.find(
            member => member.user_id === session.user.id
          );
          setIsOrgAdmin(currentUserMember?.role === 'admin');
        }

        // Store original values
        setOriginalName(organization.name);
        setOriginalType(organization.type);
        setOriginalMembers(organization.members);
        setOriginalMcpEnabled(organization.mcp_enabled || false);
      } catch (err) {
        toast.error('Failed to load organization data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [organizationId, session?.user?.id, session?.user?.role]);

  // Separate useEffect for fetching users
  useEffect(() => {
    const fetchUsers = async () => {
      if (isOrgAdmin || isSysAdmin) {
        try {
          const usersResponse = await getUsersApi();
          setAllUsers(usersResponse.users);
        } catch (err) {
          console.error('Failed to fetch users:', err);
        }
      }
    };

    fetchUsers();
  }, [organizationId, isOrgAdmin, isSysAdmin]);

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

    try {
      await updateOrganizationApi(organizationId, { 
        name,
        type,
        members,
        mcp_enabled: mcpEnabled
      });
      await refreshOrganizations();
      
      // Update original values after successful save
      setOriginalName(name);
      setOriginalType(type);
      setOriginalMembers(members);
      setOriginalMcpEnabled(mcpEnabled);
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
        <Switch
          checked={params.value}
          onChange={(e) => handleRoleChange(params.row.id, e.target.checked ? 'admin' : 'user')}
          color="primary"
        />
      )
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      renderCell: (params: GridRenderCellParams) => (
        <IconButton
          onClick={() => handleRemoveMember(params.row.id)}
          size="small"
        >
          <DeleteIcon />
        </IconButton>
      )
    }
  ]

  // Check if form has changes
  const hasChanges = () => {
    if (name !== originalName) return true;
    if (type !== originalType) return true;
    if (mcpEnabled !== originalMcpEnabled) return true;
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
  if (!loading && !isOrgAdmin && !isSysAdmin) {
    return (
      <div className="flex items-center justify-center p-4">
        You don&apos;t have permission to edit this organization. Only organization admins and system admins can edit organizations.
      </div>
    );
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
    <div className="max-w-4xl mx-auto bg-white rounded-lg shadow p-6">
      <div className="flex flex-col h-[calc(100vh-240px)]">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-semibold">Edit Organization</h2>
          <div className="flex gap-4">
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
              onClick={() => router.push('/settings/account/organizations')}
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
                  {getAvailableOrganizationTypes(originalType).map((orgType) => (
                    <option key={orgType} value={orgType}>
                      {orgType.charAt(0).toUpperCase() + orgType.slice(1)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="mt-4">
                <div className="flex items-center">
                  <Switch
                    checked={mcpEnabled}
                    onChange={(e) => setMcpEnabled(e.target.checked)}
                    color="primary"
                    id="mcp_enabled"
                  />
                  <label htmlFor="mcp_enabled" className="ml-2 text-sm font-medium text-gray-700 flex items-center gap-2">
                    Enable MCP Server
                    <InfoTooltip 
                      title="MCP Server"
                      content={
                        <>
                          <p className="mb-2">
                            Enables Machine Communication Protocol server for this organization, allowing API access through MCP.
                          </p>
                          <p className="mb-2">
                            <strong>Note:</strong> When enabled, any user with a valid token and organization membership can use MCP to access:
                          </p>
                          <ul className="list-disc list-inside space-y-1">
                            <li>Documents</li>
                            <li>Prompts</li>
                            <li>Extractions</li>
                          </ul>
                        </>
                      }
                    />
                  </label>
                </div>
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
            <div className="flex-1 bg-white rounded-lg">
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