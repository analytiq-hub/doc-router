'use client';

import CaseDetailView from '@/components/CaseDetailView';
import { useRouteParams } from '@/utils/useRouteParams';

export default function CaseDetailPage(props: {
  params: Promise<{ organizationId: string; caseId: string }>;
}) {
  const { organizationId, caseId } = useRouteParams(props);
  return (
    <div className="p-4 max-w-6xl mx-auto">
      <CaseDetailView organizationId={organizationId} caseId={caseId} />
    </div>
  );
}
