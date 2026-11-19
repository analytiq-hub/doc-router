'use client';

import React from 'react';
import { useRouteParams } from '@/utils/useRouteParams';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import OrganizationEdit from '@/components/OrganizationEdit';

interface Props {
  params: Promise<{ organizationId: string }>;
}

export default function OrganizationUsersSettingsPage(props: Props) {
  const { organizationId } = useRouteParams(props);
  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <SettingsPageHeader title="Users" subtitle="Who is in the organization and what each may do." />
      <OrganizationEdit organizationId={organizationId} section="users" />
    </div>
  );
}