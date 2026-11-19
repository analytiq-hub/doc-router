'use client'

import React from 'react';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import AzureConfigManager from '@/components/AzureConfigManager';

const AzureConfigPage: React.FC = () => {
  return (
    <div className="flex flex-col gap-4">
      <SettingsPageHeader title="Azure setup" subtitle="Azure storage and integration settings." />
      <AzureConfigManager />
    </div>
  );
};

export default AzureConfigPage;