'use client';

import { useParams, useRouter } from 'next/navigation';
import PromptCreate from '@/components/PromptCreate';
import { useOrgCapabilityRouteGuard } from '@/hooks/useOrgPermissions';
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities';

export default function PromptEditPage() {
  const { organizationId, promptRevId } = useParams();
  const router = useRouter();
  const orgId = organizationId as string;
  const { blocked, loading } = useOrgCapabilityRouteGuard(
    `/orgs/${orgId}/prompts`,
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
        onClick={() => router.push(`/orgs/${orgId}/prompts`)}
        className="mb-4 px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
      >
        ← Back to Prompts
      </button>

      <PromptCreate organizationId={orgId} promptRevId={promptRevId as string} />
    </div>
  );
}
