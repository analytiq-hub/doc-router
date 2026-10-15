'use client'

import { use } from 'react';
import PromptList from '@/components/PromptList';
import PromptCreate from '@/components/PromptCreate';
import { useSearchParams, useRouter } from 'next/navigation';
import { useOrgCapability, useOrgCapabilityTabGuard } from '@/hooks/useOrgPermissions';
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities';

export default function PromptsPage({ params }: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = use(params);
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get('tab') || 'prompts';
  const listPath = `/orgs/${organizationId}/prompts`;
  const { hasCapability: canConfigWrite, loading: capabilitiesLoading } = useOrgCapability(
    organizationId,
    CAP_CONFIG_WRITE,
  );
  useOrgCapabilityTabGuard(organizationId, tab, 'prompt-create', listPath, CAP_CONFIG_WRITE);

  const handleTabChange = (newValue: string) => {
    if (newValue === 'prompt-create' && !canConfigWrite) {
      return;
    }
    router.push(`${listPath}?tab=${newValue}`);
  };

  return (
    <div className="p-4">
      <div className="border-b border-gray-200 mb-6">
        <div className="flex gap-8">
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
          {!capabilitiesLoading && canConfigWrite && (
            <button
              onClick={() => handleTabChange('prompt-create')}
              className={`pb-4 px-1 relative font-semibold text-base ${
                tab === 'prompt-create'
                  ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
              data-tour="prompt-create"
            >
              Create Prompt
            </button>
          )}
        </div>
      </div>

      <div className="max-w-6xl mx-auto">
        <div role="tabpanel" hidden={tab !== 'prompts'}>
          {tab === 'prompts' && <PromptList organizationId={organizationId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'prompt-create'}>
          {tab === 'prompt-create' && canConfigWrite && <PromptCreate organizationId={organizationId} />}
        </div>
      </div>
    </div>
  );
}
