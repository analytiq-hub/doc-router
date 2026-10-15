'use client';

import { useParams, useRouter } from 'next/navigation';
import FormCreate from '@/components/FormCreate';
import { useOrgCapabilityRouteGuard } from '@/hooks/useOrgPermissions';
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities';

export default function FormEditPage() {
  const { organizationId, formId } = useParams();
  const router = useRouter();
  const orgId = organizationId as string;
  const { blocked, loading } = useOrgCapabilityRouteGuard(
    `/orgs/${orgId}/forms`,
    orgId,
    CAP_CONFIG_WRITE,
  );

  if (loading || blocked) {
    return null;
  }

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <button
        type="button"
        onClick={() => router.push(`/orgs/${orgId}/forms`)}
        className="mb-4 px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
      >
        ← Back to Forms
      </button>

      <FormCreate organizationId={orgId} formId={formId as string} />
    </div>
  );
}
