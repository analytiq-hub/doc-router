'use client';

import FlowsPageClient, { type FlowsTab } from '@/pages/orgs/flows-client';
import { useSearchParams } from '@/utils/appRouter';
import { useRouteParams } from '@/utils/useRouteParams';

export type { FlowsTab };

export default function OrgFlowsPage(props: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = useRouteParams(props);
  const searchParams = useSearchParams();
  const rawTab = searchParams.get('tab') || 'flows';
  const tab: FlowsTab =
    rawTab === 'credentials' || rawTab === 'executions' ? rawTab : 'flows';
  const newFlow = searchParams.get('newFlow') === '1';
  const autoCreateCredential =
    searchParams.get('newCredential') === '1' || searchParams.get('bootstrapCredential') === '1';

  return (
    <FlowsPageClient
      organizationId={organizationId}
      tab={tab}
      newFlow={newFlow}
      autoCreateCredential={autoCreateCredential}
    />
  );
}
