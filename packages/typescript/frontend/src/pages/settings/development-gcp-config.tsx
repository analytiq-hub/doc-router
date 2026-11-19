'use client';

import React from 'react';
import GCPConfigManager from '@/components/GCPConfigManager';

const GCPConfigPage: React.FC = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">GCP Setup</h2>
      <GCPConfigManager />
    </div>
  );
};

export default GCPConfigPage;
