'use client';

import { useParams, useRouter } from 'next/navigation';
import TagCreate from '@/components/TagCreate';

export default function TagEditPage() {
  const { organizationId, tagId } = useParams();
  const router = useRouter();

  return (
    <div className="p-4 max-w-4xl mx-auto">
      {/* Back to Tabs Button */}
      <button
        onClick={() => router.push(`/orgs/${organizationId}/tags`)}
        className="mb-4 px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
      >
        ← Back to Tags
      </button>

      <TagCreate organizationId={organizationId as string} tagId={tagId as string} />
    </div>
  );
}

