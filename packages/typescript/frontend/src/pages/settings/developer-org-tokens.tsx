'use client'

import React from 'react';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import OrganizationTokenManager from '@/components/OrganizationTokenManager';

const OrganizationTokensPage: React.FC = () => {
  return (
    <div className="flex flex-col gap-4">
      <SettingsPageHeader
        title="Organization tokens"
        subtitle="API tokens scoped to the organization selected in the header."
      />
      <OrganizationTokenManager />
    </div>
  );
};

export default OrganizationTokensPage;