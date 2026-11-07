'use client';

import DocumentViewerPage from '@/components/doc/DocumentViewerPage';
import { useRouteParams } from '@/utils/useRouteParams';

export default function OrgDocumentPage(props: {
  params: Promise<{ organizationId: string; id: string }>;
}) {
  const { organizationId, id } = useRouteParams(props);
  return <DocumentViewerPage organizationId={organizationId} id={id} />;
}
