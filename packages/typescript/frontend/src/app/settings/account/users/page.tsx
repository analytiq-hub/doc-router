'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import UserManager from '@/components/UserManager';

const UsersPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="system_users">
      <UserManager />
    </SettingsLayout>
  );
};

export default UsersPage; 