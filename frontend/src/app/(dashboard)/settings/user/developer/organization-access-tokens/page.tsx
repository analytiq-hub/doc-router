'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import OrganizationTokenManager from '@/components/OrganizationTokenManager';

const AccessTokensPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="user_developer">
      <div>
        <h2 className="text-xl font-semibold mb-4">Organization Token Management</h2>
        <OrganizationTokenManager />
      </div>
    </SettingsLayout>
  );
};

export default AccessTokensPage; 