'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import type { DocumentFlowResultItem } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api';
import { IoViewer } from '@/components/flows/IoViewer';

interface Props {
  organizationId: string;
  id: string;
  onHasResults?: (hasResults: boolean) => void;
}

function formatTimestamp(iso: string): string {
  const d = Date.parse(iso);
  if (!Number.isFinite(d)) return iso;
  return new Date(d).toLocaleString();
}

const PDFFlowsSidebar = ({ organizationId, id, onHasResults }: Props) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [results, setResults] = useState<DocumentFlowResultItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const res = await docRouterOrgApi.listDocumentFlowResults({ documentId: id });
        if (cancelled) return;
        setResults(res.results ?? []);
        onHasResults?.((res.results ?? []).length > 0);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Failed to load flow results');
        setResults([]);
        onHasResults?.(false);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [docRouterOrgApi, id, onHasResults]);

  if (loading) {
    return <div className="p-4 text-sm text-gray-500">Loading flow results…</div>;
  }

  if (error) {
    return <div className="p-4 text-sm text-red-600">{error}</div>;
  }

  if (results.length === 0) {
    return null;
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="divide-y divide-gray-200">
        {results.map((item) => (
          <section key={item.flow_id} className="p-4 space-y-3">
            <div className="space-y-1">
              <Link
                href={`/orgs/${organizationId}/flows/${item.flow_id}`}
                className="text-sm font-semibold text-blue-700 hover:underline"
              >
                {item.flow_name}
              </Link>
              {item.execution_id ? (
                <div>
                  <Link
                    href={`/orgs/${organizationId}/flows/${item.flow_id}?tab=executions`}
                    className="text-xs text-gray-500 hover:text-gray-800 hover:underline"
                  >
                    {formatTimestamp(item.updated_at)}
                  </Link>
                </div>
              ) : (
                <div className="text-xs text-gray-500">{formatTimestamp(item.updated_at)}</div>
              )}
            </div>
            <IoViewer
              title="Result"
              value={item.result}
              dragSource={{ nodeId: `flow-result-${item.flow_id}`, source: 'nodeOutput' }}
              defaultMode="schema"
              hideHeader={false}
            />
          </section>
        ))}
      </div>
    </div>
  );
};

export default PDFFlowsSidebar;
