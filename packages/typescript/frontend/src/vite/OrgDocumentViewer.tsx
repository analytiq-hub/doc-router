import { useParams } from 'react-router-dom';

import DocumentViewerPage from '@/components/doc/DocumentViewerPage';

export function OrgDocumentViewer() {
  const { organizationId, id } = useParams();
  if (!organizationId || !id) return null;
  return <DocumentViewerPage organizationId={organizationId} id={id} />;
}
