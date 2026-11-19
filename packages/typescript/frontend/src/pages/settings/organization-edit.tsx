'use client'

import React from 'react';
import { useRouteParams } from '@/utils/useRouteParams';
import OrganizationEdit from '@/components/OrganizationEdit';

interface OrganizationEditPageProps {
  params: Promise<{
    organizationId: string;
  }>;
}

const OrganizationEditPage: React.FC<OrganizationEditPageProps> = (props) => {
  const { organizationId } = useRouteParams(props);
  return <OrganizationEdit organizationId={organizationId} />;
};

export default OrganizationEditPage; 