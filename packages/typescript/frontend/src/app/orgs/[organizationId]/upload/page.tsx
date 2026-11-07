'use client';

import UploadPageClient from '@/pages/orgs/upload-client';
import { useRouteParams } from '@/utils/useRouteParams';

export default function UploadPage(props: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = useRouteParams(props);
  return <UploadPageClient organizationId={organizationId} />;
}
