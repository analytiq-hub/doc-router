'use client';

import { useParams, useRouter } from 'next/navigation';
import TagCreate from '@/components/TagCreate';
import { useOrgCapabilityRouteGuard } from '@/hooks/useOrgPermissions';
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities';

export default function TagEditPage() {
  const { organizationId, tagId } = useParams();
  const router = useRouter();
  const orgId = organizationId as string;
  const { blocked, loading } = useOrgCapabilityRouteGuard(
    `/orgs/${orgId}/tags`,
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
        onClick={() => router.push(`/orgs/${orgId}/tags`)}
        className="mb-4 px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
      >
        ← Back to Tags
      </button>

      <TagCreate organizationId={orgId} tagId={tagId as string} />
    </div>
  );
}
