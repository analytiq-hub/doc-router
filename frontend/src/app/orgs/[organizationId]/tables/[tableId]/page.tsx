'use client';

import { useParams, useRouter } from 'next/navigation';
import TableCreate from '@/components/TableCreate';

export default function TableEditPage() {
  const { organizationId, tableId } = useParams();
  const router = useRouter();

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <button
        onClick={() => router.push(`/orgs/${organizationId}/tables`)}
        className="mb-4 px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
      >
        ← Back to Tables
      </button>

      <TableCreate organizationId={organizationId as string} tableId={tableId as string} />
    </div>
  );
}