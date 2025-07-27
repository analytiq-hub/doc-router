'use client'

import React from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
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
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <UserAcceptInvitation token={token} />
    </div>
  );
};

export default AcceptInvitationPage; 