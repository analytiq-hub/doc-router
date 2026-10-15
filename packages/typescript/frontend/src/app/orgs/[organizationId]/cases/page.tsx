'use client';

import { use } from 'react';
import CaseList from '@/components/CaseList';
import CaseCreate from '@/components/CaseCreate';
import { useSearchParams, useRouter } from 'next/navigation';
import { useOrgCapability, useOrgCapabilityTabGuard } from '@/hooks/useOrgPermissions';
import { CAP_DOCUMENTS_WRITE } from '@/utils/orgCapabilities';

export default function CasesPage({ params }: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = use(params);
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get('tab') || 'cases';
  const listPath = `/orgs/${organizationId}/cases`;
  const { hasCapability: canWriteDocuments, loading: permissionsLoading } = useOrgCapability(
    organizationId,
    CAP_DOCUMENTS_WRITE,
  );
  useOrgCapabilityTabGuard(organizationId, tab, 'case-create', listPath, CAP_DOCUMENTS_WRITE);

  const handleTabChange = (newValue: string) => {
    if (newValue === 'case-create' && !canWriteDocuments) {
      return;
    }
    router.push(`${listPath}?tab=${newValue}`);
  };

  return (
    <div className="p-4">
      <div className="border-b border-gray-200 mb-6">
        <div className="flex gap-8">
          <button
            onClick={() => handleTabChange('cases')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'cases'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Cases
          </button>
          {!permissionsLoading && canWriteDocuments && (
            <button
              onClick={() => handleTabChange('case-create')}
              className={`pb-4 px-1 relative font-semibold text-base ${
                tab === 'case-create'
                  ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Create case
            </button>
          )}
        </div>
      </div>
      <div className="max-w-6xl mx-auto">
        <div role="tabpanel" hidden={tab !== 'cases'}>
          {tab === 'cases' && <CaseList organizationId={organizationId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'case-create'}>
          {tab === 'case-create' && canWriteDocuments && (
            <CaseCreate organizationId={organizationId} />
          )}
        </div>
      </div>
    </div>
  );
}
