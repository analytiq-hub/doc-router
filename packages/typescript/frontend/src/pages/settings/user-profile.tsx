'use client'

import React from 'react';
import UserEdit from '@/components/UserEdit';
import { useAppSession } from '@/utils/useAppSession';

const ProfilePage: React.FC = () => {
  const { session, status } = useAppSession();

  if (status === "loading") {
    return <div>Loading...</div>;
  }

  return (
    <div>
      {session?.user?.id && <UserEdit userId={session.user.id} />}
    </div>
  );
};

export default ProfilePage;