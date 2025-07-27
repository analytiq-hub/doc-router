'use client';

import { useParams, useRouter } from 'next/navigation';
import FormCreate from '@/components/FormCreate';

export default function FormEditPage() {
  const { organizationId, formId } = useParams();
  const router = useRouter();

  return (
    <div className="p-4 max-w-4xl mx-auto">
      {/* Back to Forms Button */}
      <button
        onClick={() => router.push(`/orgs/${organizationId}/forms`)}
        className="mb-4 px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
      >
        ← Back to Forms
      </button>

      <FormCreate organizationId={organizationId as string} formId={formId as string} />
    </div>
  );
} 