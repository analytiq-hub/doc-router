'use client';

import { use } from 'react';
import CaseDetailView from '@/components/CaseDetailView';

export default function CaseDetailPage({
  params,
}: {
  params: Promise<{ organizationId: string; caseId: string }>;
}) {
  const { organizationId, caseId } = use(params);
  return (
    <div className="p-4 max-w-6xl mx-auto">
      <CaseDetailView organizationId={organizationId} caseId={caseId} />
    </div>
  );
}
