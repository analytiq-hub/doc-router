'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import UserEdit from '@/components/UserEdit';

const UserEditPage: React.FC<{ params: { userId: string } }> = ({ params }) => {
  return (
    <SettingsLayout selectedMenu="system_users">
      <UserEdit userId={params.userId} />
    </SettingsLayout>
  );
};

export default UserEditPage; 