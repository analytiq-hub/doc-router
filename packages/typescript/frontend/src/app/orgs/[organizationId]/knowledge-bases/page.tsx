'use client'

import { use } from 'react';
import KnowledgeBaseList from '@/components/KnowledgeBaseList';
import KnowledgeBaseCreate from '@/components/KnowledgeBaseCreate';
import KnowledgeBaseSearch from '@/components/KnowledgeBaseSearch';
import KnowledgeBaseDocuments from '@/components/KnowledgeBaseDocuments';
import KnowledgeBaseChat from '@/components/KnowledgeBaseChat';
import { useSearchParams, useRouter } from 'next/navigation';

export default function KnowledgeBasesPage({ params }: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = use(params);
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get('tab') || 'list';
  const kbId = searchParams.get('kbId');

  const handleTabChange = (newValue: string, kbIdParam?: string) => {
    const params = new URLSearchParams();
    params.set('tab', newValue);
    if (kbIdParam) {
      params.set('kbId', kbIdParam);
    }
    router.push(`/orgs/${organizationId}/knowledge-bases?${params.toString()}`);
  };

  return (
    <div className="p-2 sm:p-4">
      <div className="border-b border-gray-200 mb-4 sm:mb-6">
        <div className="flex gap-2 sm:gap-8 overflow-x-auto">
          <button
            onClick={() => handleTabChange('list')}
            className={`pb-4 px-1 relative font-semibold text-sm sm:text-base whitespace-nowrap ${
              tab === 'list'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <span className="hidden sm:inline">Knowledge Bases</span>
            <span className="sm:hidden">KB</span>
          </button>
          <button
            onClick={() => handleTabChange('create')}
            className={`pb-4 px-1 relative font-semibold text-sm sm:text-base whitespace-nowrap ${
              tab === 'create'
                ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <span className="hidden sm:inline">Create Knowledge Base</span>
            <span className="sm:hidden">Create</span>
          </button>
          {kbId && (
            <>
              <button
                onClick={() => handleTabChange('edit', kbId)}
                className={`pb-4 px-1 relative font-semibold text-sm sm:text-base whitespace-nowrap ${
                  tab === 'edit'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Edit
              </button>
              <button
                onClick={() => handleTabChange('search', kbId)}
                className={`pb-4 px-1 relative font-semibold text-sm sm:text-base whitespace-nowrap ${
                  tab === 'search'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Search
              </button>
              <button
                onClick={() => handleTabChange('documents', kbId)}
                className={`pb-4 px-1 relative font-semibold text-sm sm:text-base whitespace-nowrap ${
                  tab === 'documents'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <span className="hidden sm:inline">Documents</span>
                <span className="sm:hidden">Docs</span>
              </button>
              <button
                onClick={() => handleTabChange('chat', kbId)}
                className={`pb-4 px-1 relative font-semibold text-sm sm:text-base whitespace-nowrap ${
                  tab === 'chat'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Chat
              </button>
            </>
          )}
        </div>
      </div>

      <div className="w-full sm:max-w-7xl sm:mx-auto">
        <div role="tabpanel" hidden={tab !== 'list'}>
          {tab === 'list' && <KnowledgeBaseList organizationId={organizationId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'create'}>
          {tab === 'create' && <KnowledgeBaseCreate organizationId={organizationId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'edit'}>
          {tab === 'edit' && kbId && <KnowledgeBaseCreate organizationId={organizationId} kbId={kbId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'search'}>
          {tab === 'search' && kbId && <KnowledgeBaseSearch organizationId={organizationId} kbId={kbId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'documents'}>
          {tab === 'documents' && kbId && <KnowledgeBaseDocuments organizationId={organizationId} kbId={kbId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'chat'}>
          {tab === 'chat' && kbId && <KnowledgeBaseChat organizationId={organizationId} kbId={kbId} />}
        </div>
      </div>
    </div>
  );
}
