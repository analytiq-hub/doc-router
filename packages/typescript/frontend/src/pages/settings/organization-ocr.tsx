'use client';

import React from 'react';
import { useRouteParams } from '@/utils/useRouteParams';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';
import OrganizationEdit from '@/components/OrganizationEdit';

interface Props {
  params: Promise<{ organizationId: string }>;
}

export default function OrganizationOcrSettingsPage(props: Props) {
  const { organizationId } = useRouteParams(props);
  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <SettingsPageHeader title="OCR" subtitle="How the text of this organization's documents is extracted." />
      <OrganizationEdit organizationId={organizationId} section="ocr" />
    </div>
  );
}