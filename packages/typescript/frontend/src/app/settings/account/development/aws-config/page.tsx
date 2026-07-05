'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import AWSConfigManager from '@/components/AWSConfigManager';

const AWSConfigPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="system_development">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">AWS Setup</h2>
        <AWSConfigManager />
      </div>
    </SettingsLayout>
  );
};

export default AWSConfigPage;
