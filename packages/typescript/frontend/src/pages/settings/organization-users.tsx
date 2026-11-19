'use client';

import React from 'react';
import { useRouteParams } from '@/utils/useRouteParams';
import { PageHeader } from '@/components/PageHeader';
import OrganizationEdit from '@/components/OrganizationEdit';

interface Props {
  params: Promise<{ organizationId: string }>;
}

export default function OrganizationUsersSettingsPage(props: Props) {
  const { organizationId } = useRouteParams(props);
  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <PageHeader title="Users" subtitle="Who is in the organization and what each may do." />
      <OrganizationEdit organizationId={organizationId} section="users" />
    </div>
  );
}