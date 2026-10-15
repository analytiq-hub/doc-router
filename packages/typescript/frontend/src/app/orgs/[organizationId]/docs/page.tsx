'use client'

import { use } from 'react';
import DocumentsPageClient from './DocumentsPageClient';

export default function DocumentsPage({
  params,
}: {
  params: Promise<{ organizationId: string }>;
}) {
  const { organizationId } = use(params);
  return <DocumentsPageClient organizationId={organizationId} />;
}
