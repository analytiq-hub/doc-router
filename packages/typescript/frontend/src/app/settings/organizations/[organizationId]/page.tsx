'use client'

import { use } from 'react';
import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import OrganizationEdit from '@/components/OrganizationEdit';

interface OrganizationEditPageProps {
  params: Promise<{
    organizationId: string;
  }>;
}

const OrganizationEditPage: React.FC<OrganizationEditPageProps> = ({ params }) => {
  const { organizationId } = use(params);
  return (
    <SettingsLayout selectedMenu="organizations">
      <OrganizationEdit organizationId={organizationId} />
    </SettingsLayout>
  );
};

export default OrganizationEditPage; 