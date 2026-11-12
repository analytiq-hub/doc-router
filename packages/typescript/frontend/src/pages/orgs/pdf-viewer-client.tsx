"use client"

import DocumentViewerPage from '@/components/doc/DocumentViewerPage';

interface PDFViewerClientProps {
  organizationId: string;
  id: string;
}

/** Legacy wrapper; routes use DocumentViewerPage directly. */
export default function PDFViewerClient({ organizationId, id }: PDFViewerClientProps) {
  return <DocumentViewerPage organizationId={organizationId} id={id} />;
}
