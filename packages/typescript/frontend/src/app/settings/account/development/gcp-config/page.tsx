'use client';

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import GCPConfigManager from '@/components/GCPConfigManager';

const GCPConfigPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="system_development">
      <div>
        <h2 className="text-xl font-semibold mb-4">GCP Setup</h2>
        <GCPConfigManager />
      </div>
    </SettingsLayout>
  );
};

export default GCPConfigPage;
