'use client'

import OrgDocumentList from '@/components/OrgDocumentList';
import DocumentUpload from '@/components/DocumentUpload';
import { useSearchParams, useRouter } from '@/utils/appRouter';
import { useOrgCapability, useOrgCapabilityTabGuard } from '@/hooks/useOrgPermissions';
import { CAP_DOCUMENTS_WRITE } from '@/utils/orgCapabilities';

interface DocumentsPageClientProps {
  organizationId: string;
}

export default function DocumentsPageClient({ organizationId }: DocumentsPageClientProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get('tab') || 'documents';
  const caseIdFromQuery = searchParams.get('case_id') ?? undefined;
  const listPath = (() => {
    const query = new URLSearchParams({ tab: 'documents' });
    if (caseIdFromQuery) query.set('case_id', caseIdFromQuery);
    return `/orgs/${organizationId}/docs?${query.toString()}`;
  })();
  const { hasCapability: canUpload, loading: capabilitiesLoading } = useOrgCapability(
    organizationId,
    CAP_DOCUMENTS_WRITE,
  );
  useOrgCapabilityTabGuard(organizationId, tab, 'upload', listPath, CAP_DOCUMENTS_WRITE);

  const handleTabChange = (newValue: string) => {
    const query = new URLSearchParams({ tab: newValue });
    if (caseIdFromQuery) query.set('case_id', caseIdFromQuery);
    router.push(`/orgs/${organizationId}/docs?${query.toString()}`);
  };

  return (
    <div className="mx-auto max-w-6xl p-4">
      <div className="mb-6 border-b border-border">
        <div className="flex gap-8">
          <button
            type="button"
            onClick={() => handleTabChange('documents')}
            className={`relative px-1 pb-4 text-base font-semibold after:absolute after:right-0 after:bottom-0 after:left-0 after:h-0.5 ${
              tab === 'documents'
                ? 'text-primary after:bg-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
            data-tour="documents"
          >
            Documents
          </button>
          {!capabilitiesLoading && canUpload && (
            <button
              type="button"
              onClick={() => handleTabChange('upload')}
              className={`relative px-1 pb-4 text-base font-semibold after:absolute after:right-0 after:bottom-0 after:left-0 after:h-0.5 ${
                tab === 'upload'
                  ? 'text-primary after:bg-primary'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              data-tour="upload-documents"
            >
              Upload documents
            </button>
          )}
        </div>
      </div>

      <div role="tabpanel" hidden={tab !== 'documents'}>
        {tab === 'documents' && (
          <OrgDocumentList organizationId={organizationId} initialCaseIdFilter={caseIdFromQuery} />
        )}
      </div>
      <div role="tabpanel" hidden={tab !== 'upload' || !canUpload}>
        {tab === 'upload' && canUpload && (
          <DocumentUpload organizationId={organizationId} defaultCaseId={caseIdFromQuery} />
        )}
      </div>
    </div>
  );
}
