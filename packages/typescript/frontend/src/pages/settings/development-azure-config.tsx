'use client';

import React from 'react';
import AzureConfigManager from '@/components/AzureConfigManager';

const AzureConfigPage: React.FC = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Azure Setup</h2>
      <AzureConfigManager />
    </div>
  );
};

export default AzureConfigPage;
