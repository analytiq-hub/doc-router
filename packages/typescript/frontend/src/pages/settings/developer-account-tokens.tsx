'use client'

import React from 'react';
import AccountTokenManager from '@/components/AccountTokenManager';

const AccountTokensPage: React.FC = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Account Token Management</h2>
      <AccountTokenManager />
    </div>
  );
};

export default AccountTokensPage; 