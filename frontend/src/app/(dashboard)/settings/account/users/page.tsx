'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import UserManager from '@/components/UserManager';

const UsersPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="system_users">
      <div>
        <h2 className="text-xl font-semibold mb-4">User Management</h2>
        <UserManager />
      </div>
    </SettingsLayout>
  );
};

export default UsersPage; 