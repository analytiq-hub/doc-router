'use client';

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import AzureConfigManager from '@/components/AzureConfigManager';

const AzureConfigPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="system_development">
      <div>
        <h2 className="text-xl font-semibold mb-4">Azure Setup</h2>
        <AzureConfigManager />
      </div>
    </SettingsLayout>
  );
};

export default AzureConfigPage;
