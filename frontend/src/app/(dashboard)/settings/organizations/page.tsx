'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import OrganizationManager from '@/components/OrganizationManager';

const OrganizationsPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="organizations">
      <div>
        <h2 className="text-xl font-semibold mb-4">Organization Management</h2>
        <OrganizationManager />
      </div>
    </SettingsLayout>
  );
};

export default OrganizationsPage; 