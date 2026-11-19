'use client'

import React from 'react';
import AWSConfigManager from '@/components/AWSConfigManager';

const AWSConfigPage: React.FC = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">AWS Setup</h2>
      <AWSConfigManager />
    </div>
  );
};

export default AWSConfigPage;
