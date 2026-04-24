'use client'

import { use } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import FlowList from '@/components/flows/FlowList';
import FlowCreate from '@/components/flows/FlowCreate';

export default function FlowsPage({ params }: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = use(params);
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get('tab') || 'flows';

  const handleTabChange = (newValue: string) => {
    router.push(`/orgs/${organizationId}/flows?tab=${newValue}`);
  };

  return (
    <div className="p-4">
      <div className="border-b border-gray-200 mb-6">
        <div className="flex gap-8">
          <button
            onClick={() => handleTabChange('flows')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'flows'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Flows
          </button>
          <button
            onClick={() => handleTabChange('flow-create')}
            className={`pb-4 px-1 relative font-semibold text-base ${
              tab === 'flow-create'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Create Flow
          </button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto">
        <div role="tabpanel" hidden={tab !== 'flows'}>
          {tab === 'flows' && <FlowList organizationId={organizationId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'flow-create'}>
          {tab === 'flow-create' && <FlowCreate organizationId={organizationId} />}
        </div>
      </div>
    </div>
  );
}

