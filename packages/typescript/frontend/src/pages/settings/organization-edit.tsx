'use client';

import React from 'react';
import { useRouteParams } from '@/utils/useRouteParams';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import OrganizationEdit from '@/components/OrganizationEdit';

interface OrganizationEditPageProps {
  params: Promise<{
    organizationId: string;
  }>;
}

const OrganizationEditPage: React.FC<OrganizationEditPageProps> = (props) => {
  const { organizationId } = useRouteParams(props);
  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <SettingsPageHeader title="General" subtitle="The organization's name, type, and feature flags." />
      <OrganizationEdit organizationId={organizationId} section="general" />
    </div>
  );
};

export default OrganizationEditPage;