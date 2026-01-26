'use client';

import { useParams, useRouter } from 'next/navigation';
import PromptCreate from '@/components/PromptCreate';

export default function PromptEditPage() {
  const { organizationId, promptRevId } = useParams();
  const router = useRouter();

  return (
    <div className="p-4 max-w-4xl mx-auto">
      {/* Back to Prompts Button */}
      <button
        onClick={() => router.push(`/orgs/${organizationId}/prompts`)}
        className="mb-4 px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
      >
        ← Back to Prompts
      </button>

      <PromptCreate organizationId={organizationId as string} promptRevId={promptRevId as string} />
    </div>
  );
}
