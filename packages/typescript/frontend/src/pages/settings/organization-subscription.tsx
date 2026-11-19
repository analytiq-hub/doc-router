'use client'

import React from 'react';
import { useParams } from '@/utils/appRouter';
import SubscriptionManager from '@/components/SubscriptionManager';
import { useAppSession } from '@/utils/useAppSession';

export default function OrganizationSubscriptionPage() {
  const params = useParams();
  const organizationId = params.organizationId as string;
  const { session } = useAppSession();

  if (!session?.user) {
    return <div>Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <SubscriptionManager organizationId={organizationId} />
    </div>
  );
} 