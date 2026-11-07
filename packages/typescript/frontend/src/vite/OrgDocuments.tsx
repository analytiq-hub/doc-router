import { useParams } from 'react-router-dom';

import DocumentsPageClient from '@/pages/orgs/documents-client';

export function OrgDocuments() {
  const { organizationId } = useParams();
  if (!organizationId) return null;
  return <DocumentsPageClient organizationId={organizationId} />;
}
