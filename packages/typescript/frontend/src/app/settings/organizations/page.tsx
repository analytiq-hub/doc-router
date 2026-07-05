'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import OrganizationManager from '@/components/OrganizationManager';

const OrganizationsPage: React.FC = () => {
  return (
    <SettingsLayout selectedMenu="organizations">
      <OrganizationManager />
    </SettingsLayout>
  );
};

export default OrganizationsPage; 