'use client'

import DocumentsPageClient from '@/pages/orgs/documents-client';
import { useRouteParams } from '@/utils/useRouteParams';

export default function DocumentsPage(props: {
  params: Promise<{ organizationId: string }>;
}) {
  const { organizationId } = useRouteParams(props);
  return <DocumentsPageClient organizationId={organizationId} />;
}
