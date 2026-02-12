'use client';

import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { DocRouterOrgApi } from '@/utils/api';
import { useMemo } from 'react';

interface PageProps {
  params: Promise<{ organizationId: string; formId: string }>;
}

export default function FormByIdRedirectPage({ params }: PageProps) {
  const { organizationId, formId } = use(params);
  const router = useRouter();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const redirect = async () => {
      try {
        const response = await docRouterOrgApi.listFormVersions({ formId });
        const sorted = response.forms.sort((a, b) => b.form_version - a.form_version);
        const latest = sorted[0];
        if (latest?.form_revid) {
          router.replace(`/orgs/${organizationId}/forms/${latest.form_revid}`);
        } else {
          setError('Form not found');
        }
      } catch (err) {
        console.error('Failed to resolve form by ID:', err);
        setError('Failed to load form');
      }
    };

    if (formId) {
      redirect();
    }
  }, [organizationId, formId, docRouterOrgApi, router]);

  if (error) {
    return (
      <div className="p-4 text-red-600">
        {error}
        <br />
        <button
          type="button"
          onClick={() => router.push(`/orgs/${organizationId}/forms`)}
          className="mt-2 text-blue-600 underline"
        >
          Back to Forms
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 flex items-center gap-2">
      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600" />
      Redirecting to form…
    </div>
  );
}
