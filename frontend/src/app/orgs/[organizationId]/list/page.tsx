'use client'

import DocumentList from '@/components/DocumentList';
import Tags from '@/components/Tags';
import { useSearchParams, useRouter } from 'next/navigation';

export default function DocumentsPage({ params }: { params: { organizationId: string } }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get('tab') || 'documents';

  const handleTabChange = (newValue: string) => {
    router.push(`/orgs/${params.organizationId}/list?tab=${newValue}`);
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
          >
            Documents
          </button>
          <button
            onClick={() => handleTabChange('tags')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'tags'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Tags
          </button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto">
        <div role="tabpanel" hidden={tab !== 'documents'}>
          {tab === 'documents' && <DocumentList organizationId={params.organizationId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'tags'}>
          {tab === 'tags' && <Tags organizationId={params.organizationId} />}
        </div>
      </div>
    </div>
  );
}