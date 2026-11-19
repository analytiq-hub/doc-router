'use client';

import React from 'react';
import SystemSettingsManager from '@/components/SystemSettingsManager';

const WorkerSettingsPage: React.FC = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Worker Settings</h2>
      <SystemSettingsManager />
    </div>
  );
};

export default WorkerSettingsPage;
