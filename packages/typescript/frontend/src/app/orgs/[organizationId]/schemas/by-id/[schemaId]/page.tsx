'use client';

import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { DocRouterOrgApi } from '@/utils/api';
import { useMemo } from 'react';

interface PageProps {
  params: Promise<{ organizationId: string; schemaId: string }>;
}

export default function SchemaByIdRedirectPage({ params }: PageProps) {
  const { organizationId, schemaId } = use(params);
  const router = useRouter();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const redirect = async () => {
      try {
        const response = await docRouterOrgApi.listSchemaVersions({ schemaId });
        const sorted = response.schemas.sort((a, b) => b.schema_version - a.schema_version);
        const latest = sorted[0];
        if (latest?.schema_revid) {
          router.replace(`/orgs/${organizationId}/schemas/${latest.schema_revid}`);
        } else {
          setError('Schema not found');
        }
      } catch (err) {
        console.error('Failed to resolve schema by ID:', err);
        setError('Failed to load schema');
      }
    };

    if (schemaId) {
      redirect();
    }
  }, [organizationId, schemaId, docRouterOrgApi, router]);

  if (error) {
    return (
      <div className="p-4 text-red-600">
        {error}
        <br />
        <button
          type="button"
          onClick={() => router.push(`/orgs/${organizationId}/schemas`)}
          className="mt-2 text-blue-600 underline"
        >
          Back to Schemas
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 flex items-center gap-2">
      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600" />
      Redirecting to schema…
    </div>
  );
}
