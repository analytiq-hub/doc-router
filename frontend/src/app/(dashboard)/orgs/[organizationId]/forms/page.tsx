'use client'

import FormList from '@/components/FormList';
import FormCreate from '@/components/FormCreate';
import { useSearchParams, useRouter } from 'next/navigation';

export default function FormsPage({ params }: { params: { organizationId: string } }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get('tab') || 'forms';

  const handleTabChange = (newValue: string) => {
    router.push(`/orgs/${params.organizationId}/forms?tab=${newValue}`);
  };

  return (
      <div className="p-4">
        <div className="border-b border-gray-200 mb-6">
          <div className="flex gap-8">
            <button
              onClick={() => handleTabChange('forms')}
              className={`pb-4 px-1 relative font-semibold text-base ${
                tab === 'forms'
                  ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Forms
            </button>
            <button
              onClick={() => handleTabChange('form-create')}
              className={`pb-4 px-1 relative font-semibold text-base ${
                tab === 'form-create'
                  ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
              data-tour="form-create"
            >
              Create Form
            </button>
          </div>
        </div>

        <div className="max-w-6xl mx-auto">
          <div role="tabpanel" hidden={tab !== 'forms'}>
            {tab === 'forms' && <FormList organizationId={params.organizationId} />}
          </div>
          <div role="tabpanel" hidden={tab !== 'form-create'}>
            {tab === 'form-create' && <FormCreate organizationId={params.organizationId} />}
          </div>
        </div>
      </div>
  );
}
