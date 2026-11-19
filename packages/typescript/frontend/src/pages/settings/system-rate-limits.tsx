'use client';

import React from 'react';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import SystemSettingsManager from '@/components/SystemSettingsManager';

const SystemRateLimitsPage: React.FC = () => {
  return (
    <div className="flex flex-col gap-4">
      <SettingsPageHeader
        title="Rate limits"
        subtitle="Per-pod Textract concurrency. LLM limits are configured on the models table."
      />
      <SystemSettingsManager section="limits" />
    </div>
  );
};

export default SystemRateLimitsPage;