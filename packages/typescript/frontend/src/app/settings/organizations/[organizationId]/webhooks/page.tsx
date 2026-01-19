'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Webhooks are now managed from Settings -> User -> Developer -> Organization Webhooks.
 * Keep this route as a backward-compatible entry point.
 */
const OrganizationWebhooksPage = () => {
  const router = useRouter();

  useEffect(() => {
    router.replace('/settings/user/developer/organization-webhooks');
  }, [router]);

  return null;
};

export default OrganizationWebhooksPage;

