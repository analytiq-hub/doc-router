'use client'

import React from 'react';
import { useRouteParams } from '@/utils/useRouteParams';
import SettingsLayout from '@/components/SettingsLayout';
import OrganizationEdit from '@/components/OrganizationEdit';

interface OrganizationEditPageProps {
  params: Promise<{
    organizationId: string;
  }>;
}

const OrganizationEditPage: React.FC<OrganizationEditPageProps> = (props) => {
  const { organizationId } = useRouteParams(props);
  return (
    <SettingsLayout selectedMenu="organizations">
      <OrganizationEdit organizationId={organizationId} />
    </SettingsLayout>
  );
};

export default OrganizationEditPage; 