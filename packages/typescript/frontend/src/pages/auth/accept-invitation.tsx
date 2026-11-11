'use client'

import React from 'react';
import { useSearchParams, useRouter } from '@/utils/appRouter';
import UserAcceptInvitation from '@/components/UserAcceptInvitation';
import { toast } from 'react-toastify';

const AcceptInvitationPage = () => {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get('token');

  if (!token) {
    toast.error('Invalid invitation link');
    router.push('/auth/signin');
    return null;
  }

  return (
    <div className="flex min-h-screen flex-col justify-center bg-gray-50 py-12 sm:px-6 lg:px-8">
      <UserAcceptInvitation token={token} />
    </div>
  );
};

export default AcceptInvitationPage; 