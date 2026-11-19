'use client'

import React from 'react';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import AWSConfigManager from '@/components/AWSConfigManager';

const AWSConfigPage: React.FC = () => {
  return (
    <div className="flex flex-col gap-4">
      <SettingsPageHeader
        title="AWS setup"
        subtitle="Credentials and S3 bucket for on-prem document storage."
      />
      <AWSConfigManager />
    </div>
  );
};

export default AWSConfigPage;