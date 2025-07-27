'use client'

import SchemaList from '@/components/SchemaList';
import PromptList from '@/components/PromptList';
import { useSearchParams, useRouter } from 'next/navigation';

export default function ModelsPage({ params }: { params: { organizationId: string } }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get('tab') || 'schemas';

  const handleTabChange = (newValue: string) => {
    router.push(`/orgs/${params.organizationId}/models?tab=${newValue}`);
  };

  return (
    <div className="container mx-auto p-4">
      <div className="border-b border-gray-200 mb-6">
        <div className="flex gap-8">
          <button
            onClick={() => handleTabChange('schemas')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'schemas'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Schemas
          </button>
          <button
            onClick={() => handleTabChange('prompts')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'prompts'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Prompts
          </button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto">
        <div role="tabpanel" hidden={tab !== 'schemas'}>
          {tab === 'schemas' && <SchemaList organizationId={params.organizationId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'prompts'}>
          {tab === 'prompts' && <PromptList organizationId={params.organizationId} />}
        </div>
      </div>
    </div>
  );
}
