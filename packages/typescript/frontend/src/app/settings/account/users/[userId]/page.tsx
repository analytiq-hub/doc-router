'use client'

import { use } from 'react';
import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import UserEdit from '@/components/UserEdit';

const UserEditPage: React.FC<{ params: Promise<{ userId: string }> }> = ({ params }) => {
  const { userId } = use(params);
  return (
    <SettingsLayout selectedMenu="system_users">
      <UserEdit userId={userId} />
    </SettingsLayout>
  );
};

export default UserEditPage; 