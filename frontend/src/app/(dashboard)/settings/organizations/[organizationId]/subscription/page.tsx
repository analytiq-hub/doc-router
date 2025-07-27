'use client'

import React from 'react';
import { useParams } from 'next/navigation';
import SubscriptionManager from '@/components/SubscriptionManager';
import { useAppSession } from '@/utils/useAppSession';
import SettingsLayout from '@/components/SettingsLayout';

export default function OrganizationSubscriptionPage() {
  const params = useParams();
  const organizationId = params.organizationId as string;
  const { session } = useAppSession();

  if (!session?.user) {
    return <div>Loading...</div>;
  }

  return (
    <SettingsLayout>
      {/* <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Billing</h1>
        <p className="text-gray-600 mt-2">
          Manage your subscription plans, usage, and billing preferences.
        </p>
      </div> */}

      <div className="space-y-6">
        <SubscriptionManager organizationId={organizationId} />
      </div>
    </SettingsLayout>
  );
} 