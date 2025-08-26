'use client'

import LambdaList from '@/components/LambdaList';
import LambdaCreate from '@/components/LambdaCreate';
import { useSearchParams, useRouter } from 'next/navigation';

export default function LambdaPage({ params }: { params: { organizationId: string } }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get('tab') || 'functions';

  const handleTabChange = (newValue: string) => {
    router.push(`/orgs/${params.organizationId}/lambda?tab=${newValue}`);
  };

  return (
    <div className="p-4">
      <div className="border-b border-gray-200 mb-6">
        <div className="flex gap-8">
          <button
            onClick={() => handleTabChange('functions')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'functions'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Lambda Functions
          </button>
          <button
            onClick={() => handleTabChange('function-create')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'function-create'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Create Function
          </button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto">
        <div role="tabpanel" hidden={tab !== 'functions'}>
          {tab === 'functions' && <LambdaList organizationId={params.organizationId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'function-create'}>
          {tab === 'function-create' && <LambdaCreate organizationId={params.organizationId} />}
        </div>
      </div>
    </div>
  );
}