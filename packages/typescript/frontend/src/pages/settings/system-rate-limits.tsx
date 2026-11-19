'use client';

import React from 'react';
import SystemSettingsManager from '@/components/SystemSettingsManager';

const SystemRateLimitsPage: React.FC = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Rate limits</h2>
      <SystemSettingsManager section="limits" />
    </div>
  );
};

export default SystemRateLimitsPage;