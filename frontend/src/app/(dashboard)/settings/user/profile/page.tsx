'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import UserEdit from '@/components/UserEdit';
import { useAppSession } from '@/utils/useAppSession';

const ProfilePage: React.FC = () => {
  const { session, status } = useAppSession();

  if (status === "loading") {
    return <div>Loading...</div>;
  }

  return (
    <SettingsLayout selectedMenu="user_profile">
      <div>
        {session?.user?.id && <UserEdit userId={session.user.id} />}
      </div>
    </SettingsLayout>
  );
};

export default ProfilePage;