'use client';

import FlowDetailPageClient from '@/pages/orgs/flow-detail-client';
import { useRouteParams } from '@/utils/useRouteParams';

export default function OrgFlowDetailPage(props: {
  params: Promise<{ organizationId: string; flowId: string }>;
}) {
  const { organizationId, flowId } = useRouteParams(props);
  return (
    <FlowDetailPageClient
      key={`${organizationId}:${flowId}`}
      organizationId={organizationId}
      flowId={flowId}
    />
  );
}
