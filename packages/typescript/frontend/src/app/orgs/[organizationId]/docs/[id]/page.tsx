'use client';

import { use } from 'react';
import DocumentViewerPage from '@/components/doc/DocumentViewerPage';

export default function OrgDocumentPage({
  params,
}: {
  params: Promise<{ organizationId: string; id: string }>;
}) {
  const { organizationId, id } = use(params);
  return <DocumentViewerPage organizationId={organizationId} id={id} />;
}
