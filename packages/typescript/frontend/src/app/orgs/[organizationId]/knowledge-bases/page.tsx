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
  const tab = searchParams.get('tab') || 'knowledge-bases';
  const kbId = searchParams.get('kbId');

  const handleTabChange = (newValue: string, kbIdParam?: string) => {
    const params = new URLSearchParams();
    params.set('tab', newValue);
    if (kbIdParam) {
      params.set('kbId', kbIdParam);
    }
    router.push(`/orgs/${organizationId}/knowledge-bases?${params.toString()}`);
  };

  const handleBack = () => {
    router.push(`/orgs/${organizationId}/knowledge-bases?tab=knowledge-bases`);
  };

  return (
    <div className="p-4">
      {kbId && (
        <div className="max-w-6xl mx-auto mb-4">
          <button
            onClick={handleBack}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
          >
            ← Back to Knowledge Bases
          </button>
        </div>
      )}
      <div className="border-b border-gray-200 mb-6">
        <div className="flex gap-8">
          {!kbId && (
            <>
              <button
                onClick={() => handleTabChange('knowledge-bases')}
                className={`pb-4 px-1 relative font-semibold text-base ${
                  tab === 'knowledge-bases'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Knowledge Bases
              </button>
              <button
                onClick={() => handleTabChange('kb-create')}
                className={`pb-4 px-1 relative font-semibold text-base ${
                  tab === 'kb-create'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Create Knowledge Base
              </button>
            </>
          )}
          {kbId && (
            <>
              <button
                onClick={() => handleTabChange('edit', kbId)}
                className={`pb-4 px-1 relative font-semibold text-base ${
                  tab === 'edit'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Edit
              </button>
              <button
                onClick={() => handleTabChange('search', kbId)}
                className={`pb-4 px-1 relative font-semibold text-base ${
                  tab === 'search'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Search
              </button>
              <button
                onClick={() => handleTabChange('documents', kbId)}
                className={`pb-4 px-1 relative font-semibold text-base ${
                  tab === 'documents'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Documents
              </button>
              <button
                onClick={() => handleTabChange('chat', kbId)}
                className={`pb-4 px-1 relative font-semibold text-base ${
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

      <div className="max-w-6xl mx-auto">
        <div role="tabpanel" hidden={tab !== 'knowledge-bases'}>
          {tab === 'knowledge-bases' && <KnowledgeBaseList organizationId={organizationId} />}
        </div>
        <div role="tabpanel" hidden={tab !== 'kb-create'}>
          {tab === 'kb-create' && <KnowledgeBaseCreate organizationId={organizationId} />}
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
