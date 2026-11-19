'use client';

import React from 'react';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import SystemSettingsManager from '@/components/SystemSettingsManager';

const SystemQueuesPage: React.FC = () => {
  return (
    <div className="flex flex-col gap-4">
      <SettingsPageHeader
        title="Queues"
        subtitle="Worker counts per queue type in each queue-worker process."
      />
      <SystemSettingsManager section="queues" />
    </div>
  );
};

export default SystemQueuesPage;