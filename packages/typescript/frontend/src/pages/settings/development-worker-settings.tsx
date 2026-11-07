'use client';

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import SystemSettingsManager from '@/components/SystemSettingsManager';

const WorkerSettingsPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="system_development">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Worker Settings</h2>
        <SystemSettingsManager />
      </div>
    </SettingsLayout>
  );
};

export default WorkerSettingsPage;
