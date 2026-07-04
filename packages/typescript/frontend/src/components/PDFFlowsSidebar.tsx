'use client';

import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { ChevronDownIcon } from '@heroicons/react/24/outline';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import { Menu, MenuItem } from '@mui/material';
import { styled, alpha } from '@mui/material/styles';
import type { FlowDocumentResult, FlowListItem } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api';
import { getStatusFromError, pollFlowRerunUntilDone } from '@/utils/flowRerunPoll';
import { IoViewer } from '@/components/flows/IoViewer';

interface Props {
  organizationId: string;
  id: string;
  /** True when the Flows sidebar tab is the active panel (not Extraction/Forms). */
  panelActive: boolean;
  onHasFlows?: (hasFlows: boolean) => void;
}

const StyledMenuItem = styled(MenuItem)(({ theme }) => ({
  fontSize: '0.875rem',
  padding: '4px 16px',
  '& .MuiSvgIcon-root': {
    color: alpha(theme.palette.text.primary, 0.6),
  },
}));

function formatTimestamp(iso: string): string {
  const d = Date.parse(iso);
  if (!Number.isFinite(d)) return iso;
  return new Date(d).toLocaleString();
}

function flowResultDownloadFilename(flowName: string, flowId: string): string {
  const slug = flowName.trim().toLowerCase().replace(/\s+/g, '_').replace(/[^\w.-]/g, '') || 'flow';
  return `${slug}_${flowId}_result.json`;
}

/** 0 = show all; 1 = hide Inactive; 2 = hide version too */
type FlowTabCompressionLevel = 0 | 1 | 2;

const FLOW_TAB_MIN_TEXT_WIDTH_PX = 72;

interface FlowTabHeaderProps {
  organizationId: string;
  flowId: string;
  flowName: string;
  tabVersion: number | undefined;
  isActive: boolean;
  isRunning: boolean;
  captured: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  onRerun: () => void;
  onOpenKebab: (e: React.MouseEvent<HTMLElement>) => void;
}

const FlowTabHeader: React.FC<FlowTabHeaderProps> = ({
  organizationId,
  flowId,
  flowName,
  tabVersion,
  isActive,
  isRunning,
  captured,
  isExpanded,
  onToggle,
  onRerun,
  onOpenKebab,
}) => {
  const rowRef = useRef<HTMLDivElement>(null);
  const actionsRef = useRef<HTMLDivElement>(null);
  const [compression, setCompression] = useState<FlowTabCompressionLevel>(0);

  useEffect(() => {
    setCompression(0);
  }, [flowName, tabVersion, isActive, captured, isExpanded]);

  useLayoutEffect(() => {
    const row = rowRef.current;
    const actions = actionsRef.current;
    if (!row || !actions) return;
    const availableTextWidth = row.clientWidth - actions.clientWidth - 8;
    if (availableTextWidth >= FLOW_TAB_MIN_TEXT_WIDTH_PX || compression >= 2) return;
    setCompression((current) => (current + 1) as FlowTabCompressionLevel);
  }, [compression, flowName, tabVersion, isActive, captured, isExpanded]);

  useEffect(() => {
    const row = rowRef.current;
    if (!row || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => setCompression(0));
    ro.observe(row);
    return () => ro.disconnect();
  }, []);

  const showVersion = compression < 2 && tabVersion != null;
  const showInactive = compression < 1 && !isActive;

  return (
    <div
      ref={rowRef}
      onClick={onToggle}
      className="flex w-full min-h-[48px] cursor-pointer items-center justify-between gap-2 bg-gray-100/[0.6] px-4 py-2 transition-colors hover:bg-gray-100/[0.8]"
    >
      <span className="text-sm text-gray-900">
        <Link
          href={`/orgs/${organizationId}/flows/${flowId}`}
          onClick={(e) => e.stopPropagation()}
          className="font-medium text-blue-700 hover:underline"
          title={flowName}
        >
          {flowName}
        </Link>
        {showVersion ? (
          <span className="text-xs text-gray-500"> (v{tabVersion})</span>
        ) : null}
      </span>
      <div ref={actionsRef} className="flex shrink-0 items-center gap-2">
        {isActive ? (
          <div
            onClick={(e) => {
              e.stopPropagation();
              onRerun();
            }}
            className="cursor-pointer rounded-full p-1 transition-colors hover:bg-black/5"
            title="Re-run flow"
          >
            {isRunning ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#2B4479]/60 border-t-transparent" />
            ) : (
              <RefreshIcon fontSize="small" className="text-gray-600" />
            )}
          </div>
        ) : showInactive ? (
          <span
            className="inline-flex shrink-0 items-center rounded-md border border-gray-200 bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700"
            title="Flow is inactive — re-run is disabled"
          >
            Inactive
          </span>
        ) : null}
        {captured ? (
          <div
            onClick={(e) => {
              e.stopPropagation();
              onOpenKebab(e);
            }}
            className="cursor-pointer rounded-full p-1 transition-colors hover:bg-black/5"
            title="More actions"
          >
            <MoreVertIcon fontSize="small" className="text-gray-600" />
          </div>
        ) : null}
        <ChevronDownIcon
          className={`h-5 w-5 shrink-0 text-gray-600 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          aria-hidden
        />
      </div>
    </div>
  );
};

const PDFFlowsSidebar = ({ organizationId, id, panelActive, onHasFlows }: Props) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [flows, setFlows] = useState<FlowListItem[]>([]);
  const [flowResults, setFlowResults] = useState<Record<string, FlowDocumentResult>>({});
  const [loadingFlows, setLoadingFlows] = useState<Set<string>>(new Set());
  const [runningFlows, setRunningFlows] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedFlowId, setExpandedFlowId] = useState<string | null>(null);
  const [kebabAnchorEl, setKebabAnchorEl] = useState<null | HTMLElement>(null);
  const [kebabFlowId, setKebabFlowId] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const expandFetchGenRef = useRef(0);
  const rerunGenRef = useRef<Record<string, number>>({});

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setExpandedFlowId(null);
    setFlowResults({});
    setLoadingFlows(new Set());
    setRunningFlows(new Set());

    void (async () => {
      try {
        const res = await docRouterOrgApi.listFlows({ documentId: id, limit: 100 });
        if (cancelled) return;
        const items = res.items ?? [];
        setFlows(items);
        onHasFlows?.(items.length > 0);
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
      expandFetchGenRef.current += 1;
      rerunGenRef.current = {};
    };
  }, [docRouterOrgApi, id, onHasFlows]);

  // Collapse all rows when the Flows panel is opened (mirrors starting collapsed on each visit).
  useLayoutEffect(() => {
    if (!panelActive) return;
    expandFetchGenRef.current += 1;
    setExpandedFlowId(null);
    setFlowResults({});
  }, [panelActive, id]);

  const fetchFlowResult = useCallback(
    async (flowId: string, shouldApply?: () => boolean) => {
      const canApply = () => mountedRef.current && (shouldApply?.() ?? true);
      if (!canApply()) return null;

      setLoadingFlows((prev) => new Set(prev).add(flowId));
      try {
        const data = await docRouterOrgApi.getFlowDocumentResult({
          documentId: id,
          flowId,
        });
        if (!canApply()) return null;
        setFlowResults((prev) => ({ ...prev, [flowId]: data }));
        return data;
      } catch (e) {
        const status = getStatusFromError(e);
        if (status !== 404) {
          console.error('Error fetching flow result:', e);
        }
        return null;
      } finally {
        if (mountedRef.current) {
          setLoadingFlows((prev) => {
            const next = new Set(prev);
            next.delete(flowId);
            return next;
          });
        }
      }
    },
    [docRouterOrgApi, id],
  );

  const handleFlowToggle = (item: FlowListItem) => {
    const flowId = item.flow.flow_id;
    if (expandedFlowId === flowId) {
      expandFetchGenRef.current += 1;
      setExpandedFlowId(null);
      return;
    }

    const gen = ++expandFetchGenRef.current;
    const isCurrentExpandFetch = () => mountedRef.current && expandFetchGenRef.current === gen;

    setExpandedFlowId(flowId);
    setFlowResults((prev) => {
      const next = { ...prev };
      delete next[flowId];
      return next;
    });

    void (async () => {
      try {
        const listRes = await docRouterOrgApi.listFlows({ documentId: id, limit: 100 });
        if (!isCurrentExpandFetch()) return;
        setFlows(listRes.items ?? []);
      } catch (e) {
        if (!isCurrentExpandFetch()) return;
        console.error('Error refreshing flows list:', e);
      }

      const data = await fetchFlowResult(flowId, isCurrentExpandFetch);
      if (!data || !isCurrentExpandFetch()) return;
      setFlows((prev) =>
        prev.map((f) => (f.flow.flow_id === flowId ? { ...f, has_captured_result: true } : f)),
      );
    })();
  };

  const handleOpenKebabMenu = (e: React.MouseEvent<HTMLElement>, flowId: string) => {
    e.stopPropagation();
    setKebabAnchorEl(e.currentTarget);
    setKebabFlowId(flowId);
  };

  const handleCloseKebabMenu = () => {
    setKebabAnchorEl(null);
    setKebabFlowId(null);
  };

  const handleDownloadResult = (flowId: string) => {
    const item = flows.find((f) => f.flow.flow_id === flowId);
    const resultRow = flowResults[flowId];
    if (!item || !resultRow) return;
    const blob = new Blob([JSON.stringify(resultRow.result ?? {}, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = flowResultDownloadFilename(item.flow.name, flowId);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleRerunFlow = async (flowId: string) => {
    const gen = (rerunGenRef.current[flowId] ?? 0) + 1;
    rerunGenRef.current[flowId] = gen;
    const isCurrentRerun = () => rerunGenRef.current[flowId] === gen;

    setRunningFlows((prev) => new Set(prev).add(flowId));
    try {
      const { execution_id: execId } = await docRouterOrgApi.rerunFlowForDocument(flowId, id, {
        mode:
          typeof window !== 'undefined' &&
          sessionStorage.getItem('docrouter.bulkFlowRerunMode') === 'incomplete_only'
            ? 'incomplete_only'
            : 'force',
      });
      if (!execId?.trim() || !isCurrentRerun()) return;

      await pollFlowRerunUntilDone(docRouterOrgApi, {
        flowId,
        documentId: id,
        execId,
        shouldContinue: isCurrentRerun,
      });

      if (!isCurrentRerun()) return;

      const data = await fetchFlowResult(flowId, isCurrentRerun);
      if (data && isCurrentRerun()) {
        setFlows((prev) =>
          prev.map((f) => (f.flow.flow_id === flowId ? { ...f, has_captured_result: true } : f)),
        );
      }
    } catch (e) {
      console.error('Error re-running flow:', e);
    } finally {
      if (isCurrentRerun()) {
        setRunningFlows((prev) => {
          const next = new Set(prev);
          next.delete(flowId);
          return next;
        });
      }
    }
  };

  const flowTabVersion = (item: FlowListItem, isExpanded: boolean): number | undefined => {
    const flowId = item.flow.flow_id;
    const resultVersion = flowResults[flowId]?.flow_version;
    if (isExpanded && resultVersion != null) {
      return resultVersion;
    }
    return item.latest_revision?.flow_version ?? item.flow.flow_version;
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
        const isRunning = runningFlows.has(flowId);
        const tabVersion = flowTabVersion(item, isExpanded);
        const isActive = Boolean(item.flow.active);
        const showResult = captured || Boolean(resultRow);

        return (
          <div key={flowId} className="border-b border-black/10">
            <FlowTabHeader
              organizationId={organizationId}
              flowId={flowId}
              flowName={flowName}
              tabVersion={tabVersion}
              isActive={isActive}
              isRunning={isRunning}
              captured={showResult}
              isExpanded={isExpanded}
              onToggle={() => handleFlowToggle(item)}
              onRerun={() => void handleRerunFlow(flowId)}
              onOpenKebab={(e) => handleOpenKebabMenu(e, flowId)}
            />
            <div className={`transition-all duration-200 ease-in-out ${isExpanded ? '' : 'hidden'}`}>
              {isExpanded ? (
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
                {showResult ? (
                  isLoadingResult ? (
                    <div className="text-sm text-gray-500">Loading result…</div>
                  ) : resultRow ? (
                    <IoViewer
                      title="Result"
                      value={resultRow.result ?? {}}
                      dragSource={{ nodeId: `flow-result-${flowId}`, source: 'nodeOutput' }}
                      defaultMode="schema"
                      hideHeader={false}
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
              ) : null}
            </div>
          </div>
        );
      })}

      <Menu
        anchorEl={kebabAnchorEl}
        open={Boolean(kebabAnchorEl)}
        onClose={handleCloseKebabMenu}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        MenuListProps={{ dense: true }}
      >
        <StyledMenuItem
          onClick={() => {
            if (!kebabFlowId) return;
            handleCloseKebabMenu();
            handleDownloadResult(kebabFlowId);
          }}
        >
          <DownloadIcon fontSize="small" sx={{ mr: 1 }} />
          Download
        </StyledMenuItem>
        {kebabFlowId && flows.find((f) => f.flow.flow_id === kebabFlowId)?.flow.active ? (
          <StyledMenuItem
            onClick={() => {
              if (!kebabFlowId) return;
              handleCloseKebabMenu();
              void handleRerunFlow(kebabFlowId);
            }}
          >
            <RefreshIcon fontSize="small" sx={{ mr: 1 }} />
            Re-run
          </StyledMenuItem>
        ) : null}
      </Menu>
    </div>
  );
};

export default PDFFlowsSidebar;
