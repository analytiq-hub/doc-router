'use client'

import { useEffect } from 'react';
import DocumentList from '@/components/DocumentList';
import DocumentUpload from '@/components/DocumentUpload';
import { useSearchParams, useRouter } from 'next/navigation';
import { useOrganizationCapabilities } from '@/contexts/OrganizationContext';
import { CAP_DOCUMENTS_WRITE, hasOrgCapability } from '@/utils/orgCapabilities';

interface DocumentsPageClientProps {
  organizationId: string;
}

export default function DocumentsPageClient({ organizationId }: DocumentsPageClientProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get('tab') || 'documents';
  const caseIdFromQuery = searchParams.get('case_id') ?? undefined;
  const { capabilities, loading: capabilitiesLoading } = useOrganizationCapabilities();
  const canUpload = hasOrgCapability(capabilities, CAP_DOCUMENTS_WRITE);

  useEffect(() => {
    if (!capabilitiesLoading && tab === 'upload' && !canUpload) {
      const query = new URLSearchParams({ tab: 'documents' });
      if (caseIdFromQuery) query.set('case_id', caseIdFromQuery);
      router.replace(`/orgs/${organizationId}/docs?${query.toString()}`);
    }
  }, [capabilitiesLoading, tab, canUpload, caseIdFromQuery, organizationId, router]);

  const handleTabChange = (newValue: string) => {
    const query = new URLSearchParams({ tab: newValue });
    if (caseIdFromQuery) query.set('case_id', caseIdFromQuery);
    router.push(`/orgs/${organizationId}/docs?${query.toString()}`);
  };

  return (
    <div className="p-4">
      <div className="border-b border-gray-200 mb-6">
        <div className="flex gap-8">
          <button
            onClick={() => handleTabChange('documents')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'documents'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
            data-tour="documents"
          >
            Documents
          </button>
          {!capabilitiesLoading && canUpload && (
            <button
              onClick={() => handleTabChange('upload')}
              className={`pb-4 px-1 relative font-semibold text-base ${
                tab === 'upload'
                  ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
              data-tour="upload-documents"
            >
              Upload Documents
            </button>
          )}
        </div>
      </div>

      <div className="max-w-6xl mx-auto">
        <div role="tabpanel" hidden={tab !== 'documents'}>
          {tab === 'documents' && (
            <DocumentList
              organizationId={organizationId}
              initialCaseIdFilter={caseIdFromQuery}
            />
          )}
        </div>
        <div role="tabpanel" hidden={tab !== 'upload' || !canUpload}>
          {tab === 'upload' && canUpload && (
            <DocumentUpload organizationId={organizationId} defaultCaseId={caseIdFromQuery} />
          )}
        </div>
      </div>
    </div>
  );
}
