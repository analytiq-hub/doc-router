'use client'

import React from 'react';
import { useRouteParams } from '@/utils/useRouteParams';
import SettingsLayout from '@/components/SettingsLayout';
import UserEdit from '@/components/UserEdit';

const UserEditPage: React.FC<{ params: Promise<{ userId: string }> }> = (props) => {
  const { userId } = useRouteParams(props);
  return (
    <SettingsLayout selectedMenu="system_users">
      <UserEdit userId={userId} />
    </SettingsLayout>
  );
};

export default UserEditPage; 