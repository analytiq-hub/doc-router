'use client';

import { useParams, useRouter } from 'next/navigation';
import CaseCreate from '@/components/CaseCreate';
import { useOrgCapabilityRouteGuard } from '@/hooks/useOrgPermissions';
import { CAP_DOCUMENTS_WRITE } from '@/utils/orgCapabilities';

export default function CaseEditPage() {
  const { organizationId, caseId } = useParams();
  const router = useRouter();
  const orgId = organizationId as string;
  const listPath = `/orgs/${orgId}/cases/${encodeURIComponent(String(caseId))}`;
  const { blocked, loading } = useOrgCapabilityRouteGuard(
    listPath,
    orgId,
    CAP_DOCUMENTS_WRITE,
  );

  if (loading || blocked) {
    return null;
  }

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <button
        type="button"
        onClick={() => router.push(listPath)}
        className="mb-4 px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
      >
        ← Back to case
      </button>
      <CaseCreate organizationId={orgId} caseId={caseId as string} />
    </div>
  );
}
