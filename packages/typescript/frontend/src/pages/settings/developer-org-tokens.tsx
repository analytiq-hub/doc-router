'use client'

import React from 'react';
import OrganizationTokenManager from '@/components/OrganizationTokenManager';

const AccessTokensPage: React.FC = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Organization Token Management</h2>
      <OrganizationTokenManager />
    </div>
  );
};

export default AccessTokensPage; 