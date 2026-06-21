'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { ChevronDownIcon } from '@heroicons/react/24/outline';
import type { FlowDocumentResult, FlowListItem } from '@docrouter/sdk';
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

function getStatusFromError(err: unknown): number | undefined {
  if (err && typeof err === 'object' && 'status' in err && typeof (err as { status: unknown }).status === 'number') {
    return (err as { status: number }).status;
  }
  return undefined;
}

const PDFFlowsSidebar = ({ organizationId, id, onHasFlows }: Props) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [flows, setFlows] = useState<FlowListItem[]>([]);
  const [flowResults, setFlowResults] = useState<Record<string, FlowDocumentResult>>({});
  const [loadingFlows, setLoadingFlows] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedFlowId, setExpandedFlowId] = useState<string | null>(null);
  const flowResultsRef = useRef(flowResults);
  const loadingFlowsRef = useRef(loadingFlows);

  flowResultsRef.current = flowResults;
  loadingFlowsRef.current = loadingFlows;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setExpandedFlowId(null);
    setFlowResults({});
    setLoadingFlows(new Set());

    void (async () => {
      try {
        const res = await docRouterOrgApi.listFlows({ documentId: id, limit: 100 });
        if (cancelled) return;
        const items = res.items ?? [];
        setFlows(items);
        onHasFlows?.(items.length > 0);
        if (items.length > 0) {
          setExpandedFlowId(items[0]!.flow.flow_id);
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

  useEffect(() => {
    if (!expandedFlowId) return;
    const item = flows.find((f) => f.flow.flow_id === expandedFlowId);
    if (!item?.has_captured_result) return;
    if (flowResultsRef.current[expandedFlowId] || loadingFlowsRef.current.has(expandedFlowId)) return;

    let cancelled = false;
    setLoadingFlows((prev) => new Set(prev).add(expandedFlowId));

    void (async () => {
      try {
        const data = await docRouterOrgApi.getFlowDocumentResult({
          documentId: id,
          flowId: expandedFlowId,
        });
        if (cancelled) return;
        setFlowResults((prev) => ({ ...prev, [expandedFlowId]: data }));
      } catch (e) {
        if (cancelled) return;
        const status = getStatusFromError(e);
        if (status !== 404) {
          console.error('Error fetching flow result:', e);
        }
      } finally {
        if (!cancelled) {
          setLoadingFlows((prev) => {
            const next = new Set(prev);
            next.delete(expandedFlowId);
            return next;
          });
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [docRouterOrgApi, expandedFlowId, flows, id]);

  const handleFlowToggle = (item: FlowListItem) => {
    const flowId = item.flow.flow_id;
    setExpandedFlowId(expandedFlowId === flowId ? null : flowId);
  };

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
        const flowId = item.flow.flow_id;
        const flowName = item.flow.name;
        const isExpanded = expandedFlowId === flowId;
        const captured = Boolean(item.has_captured_result);
        const resultRow = flowResults[flowId];
        const isLoadingResult = loadingFlows.has(flowId);
        return (
          <div key={flowId} className="border-b border-black/10">
            <button
              type="button"
              onClick={() => handleFlowToggle(item)}
              className="flex w-full min-h-[48px] items-center justify-between gap-2 px-4 bg-gray-100/[0.6] hover:bg-gray-100/[0.8] transition-colors text-left"
            >
              <span className="min-w-0 flex items-center gap-2">
                <Link
                  href={`/orgs/${organizationId}/flows/${flowId}`}
                  onClick={(e) => e.stopPropagation()}
                  className="truncate text-sm font-medium text-blue-700 hover:underline"
                >
                  {flowName}
                </Link>
                <FlowStatusBadge active={Boolean(item.flow.active)} />
              </span>
              <ChevronDownIcon
                className={`h-5 w-5 shrink-0 text-gray-600 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                aria-hidden
              />
            </button>
            <div className={`transition-all duration-200 ease-in-out ${isExpanded ? '' : 'hidden'}`}>
              <div className="space-y-3 p-4">
                {resultRow?.updated_at ? (
                  <div>
                    {resultRow.execution_id ? (
                      <Link
                        href={`/orgs/${organizationId}/flows/${flowId}?tab=executions`}
                        className="text-xs text-gray-500 hover:text-gray-800 hover:underline"
                      >
                        Last run {formatTimestamp(resultRow.updated_at)}
                      </Link>
                    ) : (
                      <div className="text-xs text-gray-500">{formatTimestamp(resultRow.updated_at)}</div>
                    )}
                  </div>
                ) : null}
                {captured ? (
                  isLoadingResult ? (
                    <div className="text-sm text-gray-500">Loading result…</div>
                  ) : resultRow ? (
                    <IoViewer
                      title="Result"
                      value={resultRow.result ?? {}}
                      dragSource={{ nodeId: `flow-result-${flowId}`, source: 'nodeOutput' }}
                      defaultMode="schema"
                      hideHeader={false}
                      downloadFilename={flowResultDownloadFilename(flowName, flowId)}
                      downloadPayload={resultRow.result ?? {}}
                    />
                  ) : (
                    <div className="rounded border border-[#eceff2] bg-white p-3 text-sm text-gray-500">
                      No result available.
                    </div>
                  )
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
