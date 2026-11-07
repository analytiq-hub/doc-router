'use client'

import DocumentsPageClient from './DocumentsPageClient';
import { useRouteParams } from '@/utils/useRouteParams';

export default function DocumentsPage(props: {
  params: Promise<{ organizationId: string }>;
}) {
  const { organizationId } = useRouteParams(props);
  return <DocumentsPageClient organizationId={organizationId} />;
}
