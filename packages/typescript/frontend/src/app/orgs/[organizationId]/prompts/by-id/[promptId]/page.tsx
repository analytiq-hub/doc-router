'use client';

import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { DocRouterOrgApi } from '@/utils/api';
import { useMemo } from 'react';

interface PageProps {
  params: Promise<{ organizationId: string; promptId: string }>;
}

export default function PromptByIdRedirectPage({ params }: PageProps) {
  const { organizationId, promptId } = use(params);
  const router = useRouter();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const redirect = async () => {
      try {
        const response = await docRouterOrgApi.listPromptVersions({ promptId });
        const sorted = response.prompts.sort((a, b) => b.prompt_version - a.prompt_version);
        const latest = sorted[0];
        if (latest?.prompt_revid) {
          router.replace(`/orgs/${organizationId}/prompts/${latest.prompt_revid}`);
        } else {
          setError('Prompt not found');
        }
      } catch (err) {
        console.error('Failed to resolve prompt by ID:', err);
        setError('Failed to load prompt');
      }
    };

    if (promptId) {
      redirect();
    }
  }, [organizationId, promptId, docRouterOrgApi, router]);

  if (error) {
    return (
      <div className="p-4 text-red-600">
        {error}
        <br />
        <button
          type="button"
          onClick={() => router.push(`/orgs/${organizationId}/prompts`)}
          className="mt-2 text-blue-600 underline"
        >
          Back to Prompts
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 flex items-center gap-2">
      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600" />
      Redirecting to prompt…
    </div>
  );
}
