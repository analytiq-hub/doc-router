'use client'

import React from 'react';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import AccountTokenManager from '@/components/AccountTokenManager';

const AccountTokensPage: React.FC = () => {
  return (
    <div className="flex flex-col gap-4">
      <SettingsPageHeader
        title="Account tokens"
        subtitle="Personal API tokens for scripts and integrations (not organization-scoped)."
      />
      <AccountTokenManager />
    </div>
  );
};

export default AccountTokensPage;