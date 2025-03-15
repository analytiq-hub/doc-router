'use client'

import Tags from '@/components/Tags';
import { useSearchParams, useRouter } from 'next/navigation';

export default function TagsPage({ params }: { params: { organizationId: string } }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get('tab') || 'tags';

  const handleTabChange = (newValue: string) => {
    router.push(`/orgs/${params.organizationId}/tags?tab=${newValue}`);
  };

  return (
    <div className="p-4">
      <div className="border-b border-gray-200 mb-6">
        <div className="flex gap-8">
          <button
            onClick={() => handleTabChange('tags')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'tags'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
            data-tour="documents-tab"
          >
            Tags
          </button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto">
        <div role="tabpanel" hidden={tab !== 'tags'}>
          {tab === 'tags' && <Tags organizationId={params.organizationId} />}
        </div>
      </div>
    </div>
  );
}