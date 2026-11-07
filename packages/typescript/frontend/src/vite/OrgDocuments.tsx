import { useParams } from 'react-router-dom';

import DocumentsPageClient from '@/app/orgs/[organizationId]/docs/DocumentsPageClient';

export function OrgDocuments() {
  const { organizationId } = useParams();
  if (!organizationId) return null;
  return <DocumentsPageClient organizationId={organizationId} />;
}
