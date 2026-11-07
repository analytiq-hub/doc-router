'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import OrganizationTokenManager from '@/components/OrganizationTokenManager';

const AccessTokensPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="user_developer">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Organization Token Management</h2>
        <OrganizationTokenManager />
      </div>
    </SettingsLayout>
  );
};

export default AccessTokensPage; 