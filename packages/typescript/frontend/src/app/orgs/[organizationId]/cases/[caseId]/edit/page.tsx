'use client';

import { useParams, useRouter } from 'next/navigation';
import CaseCreate from '@/components/CaseCreate';

export default function CaseEditPage() {
  const { organizationId, caseId } = useParams();
  const router = useRouter();

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <button
        type="button"
        onClick={() =>
          router.push(`/orgs/${organizationId}/cases/${encodeURIComponent(String(caseId))}`)
        }
        className="mb-4 px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
      >
        ← Back to case
      </button>
      <CaseCreate organizationId={organizationId as string} caseId={caseId as string} />
    </div>
  );
}
