'use client';

import { useParams, useRouter } from 'next/navigation';
import SchemaCreate from '@/components/SchemaCreate';

export default function SchemaEditPage() {
  const { organizationId, schemaId } = useParams();
  const router = useRouter();

  return (
    <div className="p-4 max-w-4xl mx-auto">
      {/* Back to Schemas Button */}
      <button
        onClick={() => router.push(`/orgs/${organizationId}/schemas`)}
        className="mb-4 px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
      >
        ← Back to Schemas
      </button>

      <SchemaCreate organizationId={organizationId as string} schemaId={schemaId as string} />
    </div>
  );
} 