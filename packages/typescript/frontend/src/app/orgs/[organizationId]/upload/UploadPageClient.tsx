'use client';

import DocumentUpload from '@/components/DocumentUpload';
import { useOrgCapability, useOrgCapabilityRouteGuard } from '@/hooks/useOrgPermissions';
import { CAP_DOCUMENTS_WRITE } from '@/utils/orgCapabilities';

export default function UploadPageClient({ organizationId }: { organizationId: string }) {
  const redirectPath = `/orgs/${organizationId}/docs`;
  const { hasCapability: canUpload, loading } = useOrgCapability(
    organizationId,
    CAP_DOCUMENTS_WRITE,
  );
  useOrgCapabilityRouteGuard(redirectPath, organizationId, CAP_DOCUMENTS_WRITE);

  if (loading) {
    return null;
  }
  if (!canUpload) {
    return null;
  }
  return <DocumentUpload organizationId={organizationId} />;
}
