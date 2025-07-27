'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import AccountTokenManager from '@/components/AccountTokenManager';

const AccountTokensPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="user_developer">
      <div>
        <h2 className="text-xl font-semibold mb-4">Account Token Management</h2>
        <AccountTokenManager />
      </div>
    </SettingsLayout>
  );
};

export default AccountTokensPage; 