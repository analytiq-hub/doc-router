'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import DocumentUpload from '@/components/DocumentUpload';
import { useOrganizationCapabilities } from '@/contexts/OrganizationContext';
import { CAP_DOCUMENTS_WRITE, hasOrgCapability } from '@/utils/orgCapabilities';

export default function UploadPageClient({ organizationId }: { organizationId: string }) {
  const router = useRouter();
  const { capabilities, loading } = useOrganizationCapabilities();
  const canUpload = hasOrgCapability(capabilities, CAP_DOCUMENTS_WRITE);

  useEffect(() => {
    if (!loading && !canUpload) {
      router.replace(`/orgs/${organizationId}/docs`);
    }
  }, [loading, canUpload, organizationId, router]);

  if (loading) {
    return null;
  }
  if (!canUpload) {
    return null;
  }
  return <DocumentUpload organizationId={organizationId} />;
}
