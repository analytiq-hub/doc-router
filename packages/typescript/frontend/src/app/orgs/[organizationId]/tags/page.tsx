'use client'

import { use } from 'react';
import TagList from '@/components/TagList';
import TagCreate from '@/components/TagCreate';
import { useSearchParams, useRouter } from 'next/navigation';
import { useOrgCapability, useOrgCapabilityTabGuard } from '@/hooks/useOrgPermissions';
import { CAP_CONFIG_WRITE } from '@/utils/orgCapabilities';

export default function TagsPage({ params }: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = use(params);
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get('tab') || 'tags';
  const listPath = `/orgs/${organizationId}/tags`;
  const { hasCapability: canConfigWrite, loading: capabilitiesLoading } = useOrgCapability(
    organizationId,
    CAP_CONFIG_WRITE,
  );
  useOrgCapabilityTabGuard(organizationId, tab, 'tag-create', listPath, CAP_CONFIG_WRITE);

  const handleTabChange = (newValue: string) => {
    if (newValue === 'tag-create' && !canConfigWrite) {
      return;
    }
    router.push(`${listPath}?tab=${newValue}`);
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
          >
            Tags
          </button>
          {!capabilitiesLoading && canConfigWrite && (
            <button
              onClick={() => handleTabChange('tag-create')}
              className={`pb-4 px-1 relative font-semibold text-base ${
                tab === 'tag-create'
                  ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
              data-tour="tag-create"
            >
              Create Tag
            </button>
          )}
        </div>
      </div>

      <div className="max-w-6xl mx-auto">
        <div role="tabpanel" hidden={tab !== 'tags'}>
          {tab === 'tags' && <TagList organizationId={organizationId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'tag-create'}>
          {tab === 'tag-create' && canConfigWrite && <TagCreate organizationId={organizationId} />}
        </div>
      </div>
    </div>
  );
}
