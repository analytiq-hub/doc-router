'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import AWSCredentialsManager from '@/components/AWSCredentialsManager';

const AWSCredentialsPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="system_development">
      <div>
        <h2 className="text-xl font-semibold mb-4">AWS Credentials Management</h2>
        <AWSCredentialsManager />
      </div>
    </SettingsLayout>
  );
};

export default AWSCredentialsPage;
