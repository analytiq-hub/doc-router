'use client'

import React from 'react';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import AWSConfigManager from '@/components/AWSConfigManager';

const AWSCredentialsPage: React.FC = () => {
  return (
    <div className="flex flex-col gap-4">
      <SettingsPageHeader title="AWS setup" subtitle="Rotate or update AWS access credentials." />
      <AWSConfigManager />
    </div>
  );
};

export default AWSCredentialsPage;