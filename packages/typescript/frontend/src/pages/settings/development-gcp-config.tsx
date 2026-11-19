'use client'

import React from 'react';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import GCPConfigManager from '@/components/GCPConfigManager';

const GCPConfigPage: React.FC = () => {
  return (
    <div className="flex flex-col gap-4">
      <SettingsPageHeader
        title="GCP setup"
        subtitle="Service account and project settings for Google Cloud integrations."
      />
      <GCPConfigManager />
    </div>
  );
};

export default GCPConfigPage;