'use client'

import { toastActionError } from '@/utils/toastActionError';
import React, { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { DocRouterAccountApi } from '@/utils/api';
import { toast } from 'react-toastify';
import { useAppSession } from '@/contexts/AppSessionContext';
import { loginWithPassword, persistSessionToken } from '@/utils/backendAuth';

interface Invitation {
  email: string;
  organizationId?: string;
  organizationName?: string;
  userExists: boolean;
}

interface UserAcceptInvitationProps {
  token: string;
}

const handleExistingUserAccept = async (
  token: string,
  userName: string | undefined | null,
  organizationName: string | undefined,
  router: ReturnType<typeof useRouter>
) => {
  try {
    const docRouterAccountApi = new DocRouterAccountApi();
    await docRouterAccountApi.acceptInvitation(token, {
      name: userName || '',
      password: ''
    });
    toast.success(organizationName 
      ? `Successfully joined ${organizationName}`
      : 'Invitation accepted successfully'
    );
    router.push('/dashboard');
  } catch (error) {
    console.error('Error accepting invitation:', error);
    toastActionError('Failed to accept invitation', error);
  }
};

const UserAcceptInvitation: React.FC<UserAcceptInvitationProps> = ({ token }) => {
  const router = useRouter();
  const { session, refreshSession } = useAppSession();
  
  const [formData, setFormData] = useState({
    name: '',
    password: '',
    confirmPassword: ''
  });
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);

  useEffect(() => {
    let mounted = true;
    let autoAcceptAttempted = false;

    const fetchInvitation = async () => {
      if (!token) return;
      
      try {
        if (!invitation) {
          const invitationResp = await docRouterAccountApi.getInvitation(token);
          if (!mounted) return;

          const info = {
            email: invitationResp.email,
            organizationId: invitationResp.organization_id,
            organizationName: invitationResp.organization_name,
            userExists: invitationResp.user_exists || false
          };
          
          setInvitation(info);
        }
        
        if (!autoAcceptAttempted && 
            session?.user?.email === invitation?.email && 
            invitation?.userExists && 
            invitation?.organizationId) {
          autoAcceptAttempted = true;
          setIsSubmitting(true);
          await handleExistingUserAccept(
            token,
            session?.user?.name,
            invitation.organizationName,
            router
          );
          if (mounted) {
            setIsSubmitting(false);
          }
        }
      } catch (error) {
        if (!mounted) return;
        console.error('Error fetching invitation:', error);
        toast.error('Invalid or expired invitation');
        router.push('/auth/signin');
      }
    };

    fetchInvitation();

    return () => {
      mounted = false;
    };
  }, [token, session?.user?.email, session?.user?.name, router, invitation, docRouterAccountApi]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!invitation) {
      setError('Invalid invitation');
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    setIsSubmitting(true);
    try {
      // First accept the invitation
      await docRouterAccountApi.acceptInvitation(token, {
        name: formData.name,
        password: formData.password
      });

      toast.success('Account created successfully');
      
      // Wait a brief moment to ensure the backend has processed the account creation
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Then attempt to sign in
      const loginResult = await loginWithPassword(invitation.email, formData.password);
      await persistSessionToken(loginResult.token);
      await refreshSession();
      router.refresh();
      router.push('/dashboard');
    } catch (error) {
      console.error('Error accepting invitation:', error);
      setError(error instanceof Error ? error.message : 'Failed to accept invitation');
      toastActionError('Failed to accept invitation', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!invitation) {
    return (
      <div className="text-center">
        Loading invitation...
      </div>
    );
  }

  // If user exists and is logged in with the same email, show joining status
  if (session?.user?.email === invitation?.email && invitation.userExists) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
        <div className="sm:mx-auto sm:w-full sm:max-w-md">
          <div className="text-center">
            <h2 className="text-2xl font-semibold">
              {invitation.organizationName 
                ? `Joining ${invitation.organizationName}`
                : 'Accepting Invitation'}
            </h2>
            <p className="mt-2 text-gray-600">Please wait...</p>
          </div>
        </div>
      </div>
    );
  }

  // If user exists but is not logged in, show message to sign in
  if (invitation?.userExists) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
        <div className="sm:mx-auto sm:w-full sm:max-w-md">
          <div className="text-center">
            <h2 className="text-2xl font-semibold">Account Already Exists</h2>
            <p className="mt-2 text-gray-600">
              Please sign in with your existing account to accept this invitation.
            </p>
            <button
              onClick={() => router.push(`/auth/signin?email=${encodeURIComponent(invitation.email)}`)}
              className="mt-4 w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Sign In
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Original form for new user creation
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
          Accept Invitation
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600">
          Create your account for {invitation?.email}
          {invitation?.organizationName && (
            <> to join {invitation.organizationName}</>
          )}
        </p>
      </div>
      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
          <form className="space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                Full Name
              </label>
              <div className="mt-1">
                <input
                  id="name"
                  name="name"
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  className="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Password
              </label>
              <div className="mt-1">
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  value={formData.password}
                  onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
                  className="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700">
                Confirm Password
              </label>
              <div className="mt-1">
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  required
                  value={formData.confirmPassword}
                  onChange={(e) => setFormData(prev => ({ ...prev, confirmPassword: e.target.value }))}
                  className="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {isSubmitting ? 'Creating Account...' : 'Create Account'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default UserAcceptInvitation; 