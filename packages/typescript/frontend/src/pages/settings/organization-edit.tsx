'use client';

import React from 'react';
import { useRouteParams } from '@/utils/useRouteParams';
import { PageHeader } from '@/components/PageHeader';
import OrganizationEdit from '@/components/OrganizationEdit';

interface OrganizationEditPageProps {
  params: Promise<{
    organizationId: string;
  }>;
}

const OrganizationEditPage: React.FC<OrganizationEditPageProps> = (props) => {
  const { organizationId } = useRouteParams(props);
  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <PageHeader title="General" subtitle="The organization's name, type, and feature flags." />
      <OrganizationEdit organizationId={organizationId} section="general" />
    </div>
  );
};

export default OrganizationEditPage;