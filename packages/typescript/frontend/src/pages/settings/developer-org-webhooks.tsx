'use client';

import React from 'react';
import SettingsLayout from '@/components/SettingsLayout';
import OrganizationWebhooks from '@/components/OrganizationWebhooks';
import { useOrganization } from '@/contexts/OrganizationContext';

const OrganizationWebhooksDeveloperPage: React.FC = () => {
  const { currentOrganization, isLoading } = useOrganization();

  return (
    <SettingsLayout selectedMenu="user_developer">
      <div>
        {isLoading ? (
          <div className="text-sm text-gray-600">Loading organizations…</div>
        ) : !currentOrganization?.id ? (
          <div className="text-sm text-gray-600">
            Select an organization from the top-right organization dropdown to configure webhooks.
          </div>
        ) : (
          <OrganizationWebhooks organizationId={currentOrganization.id} />
        )}
      </div>
    </SettingsLayout>
  );
};

export default OrganizationWebhooksDeveloperPage;

