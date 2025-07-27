'use client'

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import OrganizationEdit from '@/components/OrganizationEdit';

interface OrganizationEditPageProps {
  params: {
    organizationId: string;
  };
}

const OrganizationEditPage: React.FC<OrganizationEditPageProps> = ({ params }) => {
  return (
    <SettingsLayout selectedMenu="organizations">
      <OrganizationEdit organizationId={params.organizationId} />
    </SettingsLayout>
  );
};

export default OrganizationEditPage; 