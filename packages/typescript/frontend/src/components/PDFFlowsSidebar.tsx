'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ChevronDownIcon } from '@heroicons/react/24/outline';
import type { DocumentFlowResultItem } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api';
import { IoViewer } from '@/components/flows/IoViewer';
import FlowStatusBadge from '@/components/flows/FlowStatusBadge';

interface Props {
  organizationId: string;
  id: string;
  onHasFlows?: (hasFlows: boolean) => void;
}

function formatTimestamp(iso: string): string {
  const d = Date.parse(iso);
  if (!Number.isFinite(d)) return iso;
  return new Date(d).toLocaleString();
}

function flowResultDownloadFilename(flowName: string, flowId: string): string {
  const slug = flowName.trim().toLowerCase().replace(/\s+/g, '_').replace(/[^\w.-]/g, '') || 'flow';
  return `${slug}_${flowId}_result.json`;
}

function hasCapturedResult(item: DocumentFlowResultItem): boolean {
  if (item.execution_id?.trim()) return true;
  const result = item.result;
  return Boolean(result && typeof result === 'object' && Object.keys(result).length > 0);
}

const PDFFlowsSidebar = ({ organizationId, id, onHasFlows }: Props) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [flows, setFlows] = useState<DocumentFlowResultItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedFlowId, setExpandedFlowId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setExpandedFlowId(null);

    void (async () => {
      try {
        const res = await docRouterOrgApi.listDocumentFlowResults({ documentId: id });
        if (cancelled) return;
        const items = res.results ?? [];
        setFlows(items);
        onHasFlows?.(items.length > 0);
        if (items.length > 0) {
          setExpandedFlowId(items[0]!.flow_id);
        }
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Failed to load flows');
        setFlows([]);
        onHasFlows?.(false);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [docRouterOrgApi, id, onHasFlows]);

  if (loading) {
    return <div className="p-4 text-sm text-gray-500">Loading flows…</div>;
  }

  if (error) {
    return <div className="p-4 text-sm text-red-600">{error}</div>;
  }

  if (flows.length === 0) {
    return (
      <div className="px-4 py-3 text-sm text-gray-500">
        No flows match this document&apos;s tags. Add a document event trigger with overlapping tag filters to see flows here.
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      {flows.map((item) => {
        const isExpanded = expandedFlowId === item.flow_id;
        const captured = hasCapturedResult(item);
        return (
          <div key={item.flow_id} className="border-b border-black/10">
            <button
              type="button"
              onClick={() => setExpandedFlowId(isExpanded ? null : item.flow_id)}
              className="flex w-full min-h-[48px] items-center justify-between gap-2 px-4 bg-gray-100/[0.6] hover:bg-gray-100/[0.8] transition-colors text-left"
            >
              <span className="min-w-0 flex items-center gap-2">
                <Link
                  href={`/orgs/${organizationId}/flows/${item.flow_id}`}
                  onClick={(e) => e.stopPropagation()}
                  className="truncate text-sm font-medium text-blue-700 hover:underline"
                >
                  {item.flow_name}
                </Link>
                <FlowStatusBadge active={Boolean(item.active)} />
              </span>
              <ChevronDownIcon
                className={`h-5 w-5 shrink-0 text-gray-600 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                aria-hidden
              />
            </button>
            <div className={`transition-all duration-200 ease-in-out ${isExpanded ? '' : 'hidden'}`}>
              <div className="space-y-3 p-4">
                {item.updated_at ? (
                  <div>
                    {item.execution_id ? (
                      <Link
                        href={`/orgs/${organizationId}/flows/${item.flow_id}?tab=executions`}
                        className="text-xs text-gray-500 hover:text-gray-800 hover:underline"
                      >
                        Last run {formatTimestamp(item.updated_at)}
                      </Link>
                    ) : (
                      <div className="text-xs text-gray-500">{formatTimestamp(item.updated_at)}</div>
                    )}
                  </div>
                ) : null}
                {captured ? (
                  <IoViewer
                    title="Result"
                    value={item.result ?? {}}
                    dragSource={{ nodeId: `flow-result-${item.flow_id}`, source: 'nodeOutput' }}
                    defaultMode="schema"
                    hideHeader={false}
                    downloadFilename={flowResultDownloadFilename(item.flow_name, item.flow_id)}
                    downloadPayload={item.result ?? {}}
                  />
                ) : (
                  <div className="rounded border border-[#eceff2] bg-white p-3 text-sm text-gray-500">
                    No result yet. This flow matches this document&apos;s tags but has not produced a captured result.
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default PDFFlowsSidebar;
