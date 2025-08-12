'use client';

import { useParams } from 'next/navigation';
import TableViewer from '@/components/TableViewer';

export default function TableViewPage() {
  const { organizationId, tableId } = useParams();

  if (!organizationId || !tableId) return null;

  return (
    <div className="p-4 max-w-6xl mx-auto">
      <TableViewer
        organizationId={organizationId as string}
        tableRevId={tableId as string}
      />
    </div>
  );
}
