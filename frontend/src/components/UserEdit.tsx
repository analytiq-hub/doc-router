'use client'

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getUserApi, updateUserApi, deleteUserApi, sendVerificationEmailApi, getOrganizationsApi } from '@/utils/api';
import { UserResponse, UserUpdate, Organization } from '@/types/index';
import { useSession, signOut } from 'next-auth/react';
import { toast } from 'react-hot-toast';

interface UserEditProps {
  userId: string;
}

interface PasswordChangeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (newPassword: string) => Promise<void>;
}

const PasswordChangeModal: React.FC<PasswordChangeModalProps> = ({ isOpen, onClose, onSubmit }) => {
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    try {
      await onSubmit(newPassword);
      setNewPassword('');
      setConfirmPassword('');
      onClose();
    } catch (error) {
      console.error('Password update failed:', error);
      setError('Failed to update password');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
      <div className="bg-white p-6 rounded-lg shadow-xl max-w-md w-full">
        <h3 className="text-lg font-medium mb-4">Change Password</h3>
        
        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              New Password
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Confirm Password
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Update Password
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface DeleteUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}

const DeleteUserModal: React.FC<DeleteUserModalProps> = ({ isOpen, onClose, onConfirm }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
      <div className="bg-white p-6 rounded-lg shadow-xl max-w-md w-full">
        <h3 className="text-lg font-medium mb-4">Delete User</h3>
        <p className="text-gray-600 mb-6">
          Are you sure you want to delete this user? This action cannot be undone.
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

const UserEdit: React.FC<UserEditProps> = ({ userId }) => {
  const router = useRouter();
  const { data: session } = useSession();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [name, setName] = useState('');
  const [role, setRole] = useState<string>('user');
  const [emailVerified, setEmailVerified] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string>('');
  const [organizationType, setOrganizationType] = useState<'team' | 'enterprise'>('team');

  const [originalValues, setOriginalValues] = useState({
    name: '',
    role: 'user',
    emailVerified: false,
    organization_id: '',
    organization_type: 'team' as const
  });

  const hasChanges = () => {
    return name !== originalValues.name ||
           role !== originalValues.role ||
           emailVerified !== originalValues.emailVerified;
  };

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const userData = await getUserApi(userId);
        setUser(userData);
        setName(userData.name || '');
        setRole(userData.role);
        setEmailVerified(userData.emailVerified || false);
        setOriginalValues({
          name: userData.name || '',
          role: userData.role,
          emailVerified: userData.emailVerified || false,
          organization_id: '',
          organization_type: 'team' as const
        });
      } catch (error) {
        setError('Failed to load user');
        console.error('Error fetching user:', error);
      }
    };

    fetchUser();
  }, [userId]);

  useEffect(() => {
    const fetchOrganizations = async () => {
      try {
        const response = await getOrganizationsApi();
        setOrganizations(response.organizations);
      } catch (error) {
        console.error('Error fetching organizations:', error);
      }
    };

    fetchOrganizations();
  }, []);

  const handlePasswordUpdate = async (newPassword: string) => {
    try {
      await updateUserApi(userId, { password: newPassword });
      setSuccess(true);
    } catch (error) {
      setError('Failed to update password');
      throw error; // Re-throw to be handled by modal
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    try {
      const update: UserUpdate = {
        name: name || undefined,
        role,
        emailVerified,
        organization_id: selectedOrganizationId || undefined,
        organization_type: organizationType
      };

      await updateUserApi(userId, update);
      setSuccess(true);
      
      // Update original values after successful save
      setOriginalValues({
        name: name || '',
        role,
        emailVerified,
        organization_id: selectedOrganizationId,
        organization_type: organizationType
      });
    } catch (error) {
      setError('Failed to update user');
      console.error('Error updating user:', error);
    }
  };

  const handleDeleteUser = async () => {
    try {
      await deleteUserApi(userId);
      
      // Check if deleting current user
      if (session?.user?.id === userId) {
        // Sign out if deleting self
        signOut({ callbackUrl: '/auth/signin' });
      } else {
        // Otherwise just redirect to user list
        router.push('/settings/account/users');
      }
    } catch (error) {
      setError('Failed to delete user');
      console.error('Error deleting user:', error);
    }
  };

  const handleSendVerification = async () => {
    try {
      await sendVerificationEmailApi(userId);
      setSuccess(true);
      toast.success('Verification email sent successfully');
    } catch (error) {
      setError('Failed to send verification email');
      console.error('Error sending verification email:', error);
    }
  };

  if (!user) {
    return <div>Loading...</div>;
  }

  const isAdmin = session?.user?.role === 'admin';

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold">Edit User Profile</h2>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => router.push('/settings/account/users')}
            className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!hasChanges()}
            className={`px-4 py-2 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
              ${hasChanges()
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
          >
            Save Changes
          </button>
        </div>
      </div>
      
      {error && (
        <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-md">
          {error}
        </div>
      )}
      
      {success && (
        <div className="mb-4 p-4 bg-green-50 text-green-700 rounded-md">
          User updated successfully
        </div>
      )}

      <form onSubmit={(e) => e.preventDefault()} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Email
          </label>
          <input
            type="email"
            value={user.email}
            disabled
            className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-100 text-gray-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {isAdmin && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Organization
              </label>
              <select
                value={selectedOrganizationId}
                onChange={(e) => setSelectedOrganizationId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select an organization</option>
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name} ({org.type})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Organization Type
              </label>
              <select
                value={organizationType}
                onChange={(e) => setOrganizationType(e.target.value as 'team' | 'enterprise')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="team">Team</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>

            <div className="flex items-center space-x-2">
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={role === 'admin'}
                  onChange={(e) => setRole(e.target.checked ? 'admin' : 'user')}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
              <span className="text-sm font-medium text-gray-700">Admin Role</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={emailVerified}
                    onChange={(e) => setEmailVerified(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
                <span className="text-sm font-medium text-gray-700">Email Verified</span>
              </div>

              <button
                type="button"
                onClick={handleSendVerification}
                disabled={originalValues.emailVerified}
                className={`px-4 py-2 text-sm border rounded-md transition-colors
                  ${originalValues.emailVerified 
                    ? 'text-gray-400 border-gray-400 cursor-not-allowed' 
                    : 'text-blue-600 border-blue-600 hover:bg-blue-50'
                  }`}
              >
                Send Verification Email
              </button>
            </div>
          </>
        )}

        {user.hasPassword && (
          <div className="border-t pt-4">
            <button
              type="button"
              onClick={() => setIsPasswordModalOpen(true)}
              className="px-4 py-2 text-blue-600 border border-blue-600 rounded-md hover:bg-blue-50"
            >
              Change Password
            </button>
          </div>
        )}
      </form>

      <div className="mt-8 pt-6 border-t">
        <button
          type="button"
          onClick={() => setIsDeleteModalOpen(true)}
          className="px-4 py-2 text-red-600 border border-red-600 rounded-md hover:bg-red-50"
        >
          Delete User
        </button>
      </div>

      <PasswordChangeModal
        isOpen={isPasswordModalOpen}
        onClose={() => setIsPasswordModalOpen(false)}
        onSubmit={handlePasswordUpdate}
      />

      <DeleteUserModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onConfirm={handleDeleteUser}
      />
    </div>
  );
};

export default UserEdit; 