'use client'

import AccessTokenManager from '@/components/AccessTokenManager';
import { SettingsPageHeader } from '@/components/SettingsPageHeader';

export default function AccessTokensPage() {
  return (
    <div className="flex flex-col gap-4">
      <SettingsPageHeader title="Access tokens" subtitle="Legacy personal access tokens page." />
      <AccessTokenManager />
    </div>
  );
}