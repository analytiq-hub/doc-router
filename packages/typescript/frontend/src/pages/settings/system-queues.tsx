'use client';

import React from 'react';
import SystemSettingsManager from '@/components/SystemSettingsManager';

const SystemQueuesPage: React.FC = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Queues</h2>
      <SystemSettingsManager section="queues" />
    </div>
  );
};

export default SystemQueuesPage;