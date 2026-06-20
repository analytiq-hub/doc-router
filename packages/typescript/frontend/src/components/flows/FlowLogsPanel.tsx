'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { FlowExecution, FlowPinData } from '@docrouter/sdk';
import type { Edge, Node } from 'reactflow';
import { CheckCircleIcon } from '@heroicons/react/24/solid';
import { ExclamationCircleIcon, PencilSquareIcon } from '@heroicons/react/24/outline';
import { DocRouterOrgApi } from '@/utils/api';
import { formatLocalDate } from '@/utils/date';
import { ChevronDownIcon, ChevronUpIcon, TrashIcon } from '@heroicons/react/24/outline';
import type { FlowRfNodeData } from './flowRf';
import type { FlowExecutionBlobContext } from './flowExecutionBlob';
import { buildNodeInputPreview, buildNodeOutputPreview } from './flowNodeIoPreview';
import { IoViewer } from './IoViewer';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Menu, MenuButton, MenuItem, MenuItems } from '@headlessui/react';
import { EllipsisVerticalIcon } from '@heroicons/react/24/outline';
import {
  flowWorkspaceDropdownItemSimpleClass,
  flowWorkspaceMenuPanelClass,
  flowWorkspaceMenuTriggerIconBtnClass,
} from './flowWorkspaceMenu';
import { NodeRunErrorDetails } from './flowNodeRunErrorDetails';
import { FlowNodeTracePanel, hasNodeTraceContent, traceEventCount } from './flowNodeTracePanel';
import { flowPanelColResizeHandleClass, flowPanelColResizeHitAreaMargins } from './flowUiClasses';
import {
  formatItemLineage,
  formatUpstreamSummary,
  pairedItemFromRunEntry,
} from './flowRunLineage';

function isRunning(e: FlowExecution) {
  return e.status === 'queued' || e.status === 'running';
}

type LogsTab = 'overview' | 'details';

const NODE_SPLIT_STORAGE_KEY = 'docrouter.flow.logsPanel.nodeSplit.leftPct';

type RunDataEntry = {
  status?: string;
  start_time?: string;
  execution_time_ms?: number;
  execution_index?: number;
  data?: unknown;
  error?: unknown;
  logs?: unknown;
  trace?: unknown;
  source?: unknown;
};

/** Top-level execution failure (`flow_executions.error`), when the worker/engine recorded one. */
function ExecutionErrorBanner({ error }: { error: Record<string, unknown> | null | undefined }) {
  if (!error || typeof error !== 'object') return null;
  const message = typeof error.message === 'string' ? error.message : null;
  if (message == null || message === '') return null;
  return <NodeRunErrorDetails error={error} />;
}

function formatExecutionMs(ms: number | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return '—';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)}s`;
}

function formatRunWallDuration(ex: FlowExecution): string {
  const end = ex.finished_at ? new Date(ex.finished_at).getTime() : Date.now();
  const start = new Date(ex.started_at).getTime();
  if (!Number.isFinite(end) || !Number.isFinite(start)) return '—';
  const s = Math.max(0, Math.round((end - start) / 1000));
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function nodeLabel(nodes: Node<FlowRfNodeData>[] | undefined, nodeId: string): string {
  const n = nodes?.find((x) => x.id === nodeId);
  const name = n?.data?.flowNode?.name;
  return name && name.trim() ? name : nodeId;
}

const FlowLogsPanel: React.FC<{
  orgApi: DocRouterOrgApi;
  flowId: string;
  focusExecutionId: string | null;
  onClearFocus: () => void;
  /** Called after the execution is deleted from the server (e.g. refresh execution list). */
  onExecutionDeleted?: (executionId: string) => void;
  onExecutionChange?: (e: FlowExecution | null) => void;
  onEditNode?: (nodeId: string) => void;
  expanded: boolean;
  onToggleExpanded: () => void;
  /** Current canvas graph — used for node names and input wiring in log details. */
  graphNodes?: Node<FlowRfNodeData>[];
  graphEdges?: Edge[];
  /** When set (editor), downstream input previews use pinned upstream overrides with execution data. */
  graphPinData?: FlowPinData | null;
  /** When true, disable the log-details column split (e.g. node config modal is open). */
  disableDetailSplitResize?: boolean;
}> = ({
  orgApi,
  flowId,
  focusExecutionId,
  onClearFocus,
  onExecutionDeleted,
  onExecutionChange,
  onEditNode,
  expanded,
  onToggleExpanded,
  graphNodes,
  graphEdges,
  graphPinData,
  disableDetailSplitResize = false,
}) => {
  const [execution, setExecution] = useState<FlowExecution | null>(null);
  const [activeTab, setActiveTab] = useState<LogsTab>('overview');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [ioTab, setIoTab] = useState<'input' | 'output' | 'trace'>('output');
  const [nodeSplitLeftPct, setNodeSplitLeftPct] = useState<number>(() => {
    if (typeof window === 'undefined') return 32;
    const raw = window.localStorage.getItem(NODE_SPLIT_STORAGE_KEY);
    const n = raw ? Number(raw) : NaN;
    if (!Number.isFinite(n)) return 32;
    return Math.min(60, Math.max(22, n));
  });

  const edges = useMemo(() => graphEdges ?? [], [graphEdges]);
  const nodes = useMemo(() => graphNodes ?? [], [graphNodes]);

  useEffect(() => {
    onExecutionChange?.(execution);
  }, [execution, onExecutionChange]);

  useEffect(() => {
    setSelectedNodeId(null);
    setActiveTab('overview');
    setIoTab('output');
  }, [execution?.execution_id]);

  const [err, setErr] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const downloadJson = (filename: string, data: unknown) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const onDownloadExecutionJson = useCallback(() => {
    if (!execution) return;
    try {
      setErr('');
      downloadJson(`execution_${flowId}_${execution.execution_id}.json`, execution);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to download execution JSON');
    }
  }, [execution, flowId]);

  const load = useCallback(
    async (id: string) => {
      try {
        setErr('');
        setLoading(true);
        const ex = await orgApi.getExecution(flowId, id);
        setExecution(ex);
      } catch (e: unknown) {
        setErr(e instanceof Error ? e.message : 'Failed to load execution');
        setExecution(null);
      } finally {
        setLoading(false);
      }
    },
    [orgApi, flowId],
  );

  useEffect(() => {
    if (focusExecutionId) {
      void load(focusExecutionId);
    } else {
      setExecution(null);
    }
  }, [focusExecutionId, load]);

  useEffect(() => {
    if (!execution || !isRunning(execution)) return;
    const id = setInterval(() => {
      void load(execution.execution_id);
    }, 2000);
    return () => clearInterval(id);
  }, [execution, load]);

  const onClear = () => {
    onClearFocus();
    setExecution(null);
    setSelectedNodeId(null);
    setActiveTab('overview');
    setErr('');
  };

  const onDelete = async () => {
    const id = execution?.execution_id ?? focusExecutionId;
    if (!id) {
      onClear();
      return;
    }
    if (execution && isRunning(execution)) return;
    if (!window.confirm('Delete this execution permanently?')) return;
    try {
      setDeleteLoading(true);
      setErr('');
      await orgApi.deleteExecution(flowId, id);
      onExecutionDeleted?.(id);
      onClear();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to delete execution');
    } finally {
      setDeleteLoading(false);
    }
  };

  const runData = execution?.run_data as Record<string, unknown> | undefined;

  const sortedRunEntries = useMemo(() => {
    if (!runData) return [];
    return Object.entries(runData)
      .map(([nodeId, raw]) => ({ nodeId, rec: raw as RunDataEntry }))
      .sort((a, b) => {
        const ai = a.rec.execution_index;
        const bi = b.rec.execution_index;
        if (typeof ai === 'number' && typeof bi === 'number' && ai !== bi) return ai - bi;
        return (a.rec.start_time ?? '').localeCompare(b.rec.start_time ?? '');
      });
  }, [runData]);

  useEffect(() => {
    if (!execution || execution.status !== 'error' || sortedRunEntries.length === 0) return;
    const lastId = execution.last_node_executed?.trim();
    let nodeId: string | null = null;
    if (lastId && runData?.[lastId]) {
      nodeId = lastId;
      setSelectedNodeId(lastId);
    } else {
      const failed = [...sortedRunEntries]
        .filter(({ rec }) => rec.status === 'error')
        .sort((a, b) => (b.rec.execution_index ?? 0) - (a.rec.execution_index ?? 0))[0];
      if (failed) {
        nodeId = failed.nodeId;
        setSelectedNodeId(failed.nodeId);
      }
    }
    setActiveTab('details');
    if (!nodeId) {
      setIoTab('output');
      return;
    }
    const rec = runData?.[nodeId] as RunDataEntry | undefined;
    if (
      hasNodeTraceContent({
        nodeError: rec?.error,
        executionError:
          execution.last_node_executed === nodeId && execution.error
            ? (execution.error as Record<string, unknown>)
            : null,
        traceEvents: rec?.trace,
      })
    ) {
      setIoTab('trace');
    } else {
      setIoTab('output');
    }
  }, [execution?.execution_id, execution?.status, execution?.last_node_executed, execution?.error, runData, sortedRunEntries]);

  useEffect(() => {
    if (selectedNodeId || sortedRunEntries.length === 0) return;
    const lastId = execution?.last_node_executed?.trim();
    if (lastId && runData?.[lastId]) {
      setSelectedNodeId(lastId);
      return;
    }
    setSelectedNodeId(sortedRunEntries[sortedRunEntries.length - 1].nodeId);
  }, [selectedNodeId, sortedRunEntries, execution?.last_node_executed, runData]);

  const summaryLine = useMemo(() => {
    if (!execution) return '';
    const statusLabel =
      execution.status === 'success'
        ? 'Success'
        : execution.status === 'error'
          ? 'Error'
          : execution.status === 'running'
            ? 'Running'
            : execution.status === 'queued'
              ? 'Queued'
              : execution.status === 'stopped'
                ? 'Stopped'
                : execution.status;
    const wall = formatRunWallDuration(execution);
    return `${statusLabel} in ${wall}`;
  }, [execution]);

  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return nodes.find((n) => n.id === selectedNodeId) ?? null;
  }, [nodes, selectedNodeId]);

  const selectedNodeType = selectedNode?.data?.nodeType ?? null;
  const isSelectedTrigger = Boolean(selectedNodeType?.is_trigger);

  useEffect(() => {
    if (isSelectedTrigger && ioTab === 'input') setIoTab('output');
  }, [isSelectedTrigger, ioTab]);

  const selectedRunEntry = useMemo(() => {
    if (!selectedNodeId) return null;
    const raw = runData?.[selectedNodeId];
    return raw ? (raw as RunDataEntry) : null;
  }, [runData, selectedNodeId]);

  const selectedInputPreview = useMemo(() => {
    if (!selectedNodeId) return null;
    return buildNodeInputPreview(selectedNodeId, edges, runData, graphPinData ?? undefined);
  }, [edges, graphPinData, runData, selectedNodeId]);

  const selectedOutputPreview = useMemo(() => {
    if (!selectedNodeId) return null;
    return buildNodeOutputPreview(selectedNodeId, runData, graphPinData ?? undefined);
  }, [graphPinData, runData, selectedNodeId]);

  const selectedExecutionError = useMemo((): Record<string, unknown> | null => {
    if (
      execution?.status === 'error' &&
      execution.last_node_executed === selectedNodeId &&
      execution.error &&
      typeof execution.error === 'object'
    ) {
      return execution.error as Record<string, unknown>;
    }
    return null;
  }, [execution, selectedNodeId]);

  const showTraceTab = useMemo(
    () =>
      hasNodeTraceContent({
        nodeError: selectedRunEntry?.error,
        executionError: selectedExecutionError,
        codeLogs: selectedOutputPreview?.logs,
        traceEvents: selectedRunEntry?.trace,
      }),
    [selectedRunEntry, selectedExecutionError, selectedOutputPreview?.logs],
  );

  const detailIoTabs = useMemo((): Array<'input' | 'output' | 'trace'> => {
    if (!selectedNodeId) return [];
    const base: Array<'input' | 'output'> = isSelectedTrigger ? ['output'] : ['input', 'output'];
    return showTraceTab ? [...base, 'trace'] : base;
  }, [isSelectedTrigger, selectedNodeId, showTraceTab]);

  useEffect(() => {
    if (ioTab === 'trace' && !showTraceTab) setIoTab('output');
  }, [ioTab, showTraceTab, selectedNodeId]);

  const selectedOutputLineage = useMemo(() => {
    if (!selectedRunEntry?.source) return null;
    return formatItemLineage({
      source: selectedRunEntry.source,
      pairedItem: pairedItemFromRunEntry(selectedRunEntry),
      nodes,
    });
  }, [nodes, selectedRunEntry]);

  const flowBlobDownloadContext = useMemo((): FlowExecutionBlobContext | null => {
    const eid = execution?.execution_id?.trim();
    if (!eid) return null;
    return { organizationId: orgApi.organizationId, flowId, executionId: eid };
  }, [execution?.execution_id, orgApi.organizationId, flowId]);

  const selectedParametersValue = useMemo(() => {
    const flowNode = selectedNode?.data?.flowNode;
    if (!flowNode) return null;
    return {
      name: flowNode.name,
      type: flowNode.type,
      disabled: Boolean(flowNode.disabled),
      on_error: flowNode.on_error ?? 'stop',
      parameters: flowNode.parameters ?? {},
    };
  }, [selectedNode]);

  return (
    <div className="flex h-full min-h-0 flex-col border-t border-[#e2e4e8] bg-[#fbfbfc]" data-testid="flow-logs-panel">
      <div className="flex h-11 items-center justify-between gap-2 px-3">
        <button
          type="button"
          onClick={onToggleExpanded}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <span className="text-sm font-semibold text-gray-800">Logs</span>
          {execution && (
            <span className="truncate text-xs text-gray-500">
              {formatLocalDate(execution.started_at)} · {execution.status}
            </span>
          )}
        </button>
        <div className="flex shrink-0 items-center gap-0.5">
          {execution && (
            <>
              <Menu as="div" className="relative inline-flex">
                <MenuButton className={flowWorkspaceMenuTriggerIconBtnClass} aria-label="More actions">
                  <EllipsisVerticalIcon className="h-5 w-5" aria-hidden />
                </MenuButton>
                <MenuItems anchor="bottom end" portal modal={false} className={flowWorkspaceMenuPanelClass}>
                  <MenuItem>
                    {({ focus }) => (
                      <button
                        type="button"
                        className={`${flowWorkspaceDropdownItemSimpleClass} w-full ${focus ? 'bg-gray-100' : ''}`}
                        onClick={() => onDownloadExecutionJson()}
                      >
                        Download
                      </button>
                    )}
                  </MenuItem>
                </MenuItems>
              </Menu>
            </>
          )}
          {(execution || focusExecutionId) && (
            <button
              type="button"
              title={
                execution && isRunning(execution)
                  ? 'Stop execution before deleting'
                  : 'Delete execution'
              }
              onClick={() => void onDelete()}
              disabled={deleteLoading || (execution != null && isRunning(execution))}
              aria-label="Delete execution"
              className="rounded-md p-1.5 text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <TrashIcon className="h-4 w-4" />
            </button>
          )}
          <button
            type="button"
            onClick={onToggleExpanded}
            aria-label={expanded ? 'Collapse' : 'Expand'}
            className="rounded-md p-1.5 text-gray-600 transition hover:bg-gray-100"
          >
            {expanded ? <ChevronDownIcon className="h-5 w-5" /> : <ChevronUpIcon className="h-5 w-5" />}
          </button>
        </div>
      </div>
      {expanded && (
        <div className="min-h-0 flex-1 overflow-auto border-t border-[#eceff2] bg-white">
          <div className="p-3">
            {err && <div className="mb-2 text-sm text-red-600">{err}</div>}
            {loading && !execution && <div className="text-sm text-gray-500">Loading…</div>}
            {!focusExecutionId && !execution && !loading && (
              <div className="text-sm text-gray-600">
                Run the workflow to capture an execution, or open the <strong>Executions</strong> tab for full
                history.
              </div>
            )}
            {execution && (
              <>
                <div className="mb-3 flex items-start justify-between gap-2 border-b border-[#eceff2] pb-2">
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="text-sm font-semibold text-gray-900">{summaryLine}</div>
                    <ExecutionErrorBanner error={execution.error} />
                  </div>
                  <div className="inline-flex shrink-0 rounded-md border border-gray-200 bg-white p-0.5 text-[11px]">
                    {(['overview', 'details'] as const).map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => setActiveTab(t)}
                        className={[
                          'rounded px-2 py-1 font-semibold',
                          activeTab === t ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-50',
                        ].join(' ')}
                      >
                        {t === 'overview' ? 'Overview' : 'Details'}
                      </button>
                    ))}
                  </div>
                </div>

                {sortedRunEntries.length === 0 ? (
                  <div className="text-sm text-gray-600">No node results recorded yet for this run.</div>
                ) : (
                  <div className="min-w-0">

                    {activeTab === 'overview' && (
                      <div className="overflow-hidden rounded-md border border-[#e8eaed] bg-white">
                        <ul className="divide-y divide-[#eceff2]">
                          {sortedRunEntries.map(({ nodeId, rec }) => {
                            const ok = rec.status === 'success';
                            const label = nodeLabel(nodes, nodeId);
                            const selected = nodeId === selectedNodeId;
                            const canEdit = Boolean(onEditNode) && nodes.some((n) => n.id === nodeId);
                            const started = rec.start_time ? formatLocalDate(rec.start_time) : '—';
                            const upstream = formatUpstreamSummary(rec.source, nodes);
                            const traceCount = traceEventCount(rec.trace);
                            const rawLogs = (rec as { logs?: unknown }).logs;
                            const codeLogs = Array.isArray(rawLogs)
                              ? (rawLogs.filter((x) => typeof x === 'string') as string[])
                              : [];
                            const openTraceOnSelect = hasNodeTraceContent({
                              nodeError: rec.error,
                              executionError:
                                execution?.status === 'error' &&
                                execution.last_node_executed === nodeId &&
                                execution.error
                                  ? (execution.error as Record<string, unknown>)
                                  : null,
                              codeLogs,
                              traceEvents: rec.trace,
                            });
                            return (
                              <li key={nodeId}>
                                <div
                                  role="button"
                                  tabIndex={0}
                                  onClick={() => {
                                    setSelectedNodeId(nodeId);
                                    setActiveTab('details');
                                    setIoTab(openTraceOnSelect ? 'trace' : 'output');
                                  }}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                      e.preventDefault();
                                      setSelectedNodeId(nodeId);
                                      setActiveTab('details');
                                      setIoTab(openTraceOnSelect ? 'trace' : 'output');
                                    }
                                  }}
                                  className={[
                                    'group flex min-h-[44px] w-full items-center gap-2 px-3 py-2 text-left transition',
                                    selected ? 'bg-gray-100' : 'bg-white hover:bg-gray-50',
                                  ].join(' ')}
                                >
                                  <div className="shrink-0">
                                    {ok ? (
                                      <CheckCircleIcon className="h-5 w-5 text-emerald-500" aria-hidden />
                                    ) : (
                                      <ExclamationCircleIcon className="h-5 w-5 text-red-500" aria-hidden />
                                    )}
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <div className="truncate text-sm font-medium text-gray-900">{label}</div>
                                    {upstream ? (
                                      <div className="truncate text-xs text-gray-500">{upstream}</div>
                                    ) : null}
                                  </div>

                                  {traceCount > 0 ? (
                                    <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-700">
                                      {traceCount} trace
                                    </span>
                                  ) : null}

                                  <div className="shrink-0 whitespace-nowrap text-xs text-gray-600">
                                    {formatExecutionMs(rec.execution_time_ms)}
                                  </div>
                                  <div className="shrink-0 whitespace-nowrap text-xs text-gray-500">{started}</div>

                                  {canEdit && (
                                    <span className="shrink-0 opacity-0 pointer-events-none transition group-hover:opacity-100 group-hover:pointer-events-auto">
                                      <button
                                        type="button"
                                        title="Edit"
                                        aria-label="Edit"
                                        onClick={(ev) => {
                                          ev.preventDefault();
                                          ev.stopPropagation();
                                          onEditNode?.(nodeId);
                                        }}
                                        className="rounded-md p-1.5 text-gray-600 transition hover:bg-gray-100"
                                      >
                                        <PencilSquareIcon className="h-5 w-5" />
                                      </button>
                                    </span>
                                  )}
                                </div>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    )}

                    {activeTab === 'details' && (
                      <PanelGroup
                        direction="horizontal"
                        className="flex min-h-[240px] w-full min-w-0"
                        onLayout={(sizes) => {
                          const left = sizes[0] ?? 0;
                          if (left > 0) {
                            const next = Math.min(60, Math.max(22, left));
                            setNodeSplitLeftPct(next);
                            try {
                              window.localStorage.setItem(NODE_SPLIT_STORAGE_KEY, String(next));
                            } catch {
                              // ignore
                            }
                          }
                        }}
                      >
                        <Panel defaultSize={nodeSplitLeftPct} minSize={22} className="flex min-h-0 min-w-0 flex-col overflow-hidden">
                          <div className="min-h-0 min-w-0 overflow-auto pr-1">
                            <ul className="divide-y divide-[#eceff2] rounded-md border border-[#e8eaed] bg-white">
                              {sortedRunEntries.map(({ nodeId, rec }) => {
                                const ok = rec.status === 'success';
                                const label = nodeLabel(nodes, nodeId);
                                const selected = nodeId === selectedNodeId;
                                const canEdit = Boolean(onEditNode) && nodes.some((n) => n.id === nodeId);
                                const upstream = formatUpstreamSummary(rec.source, nodes);
                                return (
                                  <li key={nodeId}>
                                    <div
                                      role="button"
                                      tabIndex={0}
                                      onClick={() => setSelectedNodeId(nodeId)}
                                      onKeyDown={(e) => {
                                        if (e.key === 'Enter' || e.key === ' ') {
                                          e.preventDefault();
                                          setSelectedNodeId(nodeId);
                                        }
                                      }}
                                      className={[
                                        'group flex min-h-[44px] w-full items-center gap-2 px-2 py-2 text-left transition sm:px-3',
                                        selected ? 'bg-gray-100' : 'bg-white hover:bg-gray-50',
                                      ].join(' ')}
                                    >
                                      <div className="shrink-0">
                                        {ok ? (
                                          <CheckCircleIcon className="h-5 w-5 text-emerald-500" aria-hidden />
                                        ) : (
                                          <ExclamationCircleIcon className="h-5 w-5 text-red-500" aria-hidden />
                                        )}
                                      </div>
                                      <div className="min-w-0 flex-1">
                                        <div className="truncate text-sm font-medium text-gray-900">{label}</div>
                                        {upstream ? (
                                          <div className="truncate text-xs text-gray-500">{upstream}</div>
                                        ) : null}
                                      </div>
                                      {canEdit && (
                                        <span className="shrink-0 opacity-0 pointer-events-none transition group-hover:opacity-100 group-hover:pointer-events-auto">
                                          <button
                                            type="button"
                                            title="Edit"
                                            aria-label="Edit"
                                            onClick={(ev) => {
                                              ev.preventDefault();
                                              ev.stopPropagation();
                                              onEditNode?.(nodeId);
                                            }}
                                            className="rounded-md p-1.5 text-gray-600 transition hover:bg-gray-100"
                                          >
                                            <PencilSquareIcon className="h-5 w-5" />
                                          </button>
                                        </span>
                                      )}
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        </Panel>
                        <PanelResizeHandle
                          disabled={disableDetailSplitResize}
                          className={flowPanelColResizeHandleClass}
                          hitAreaMargins={flowPanelColResizeHitAreaMargins}
                        />
                        <Panel defaultSize={100 - nodeSplitLeftPct} minSize={35} className="flex min-h-0 min-w-0 flex-col overflow-hidden">
                          <div className="min-h-0 min-w-0 flex-1 overflow-auto">
                            <div className="rounded-md border border-gray-200 bg-white">
                              <div className="flex items-start justify-between gap-3 border-b border-[#eceff2] px-3 py-2">
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-semibold text-gray-900">
                                    {selectedNodeId ? nodeLabel(nodes, selectedNodeId) : 'Select a node'}
                                  </div>
                                  <div className="mt-0.5 text-[11px] text-gray-500">
                                    {selectedRunEntry?.status ?? '—'}
                                    {selectedRunEntry?.execution_time_ms != null && (
                                      <span> · {formatExecutionMs(selectedRunEntry.execution_time_ms)}</span>
                                    )}
                                  </div>
                                </div>

                                {selectedNodeId && detailIoTabs.length > 0 && (
                                  <div className="inline-flex shrink-0 rounded-md border border-gray-200 bg-white p-0.5 text-[11px]">
                                    {detailIoTabs.map((t) => (
                                      <button
                                        key={t}
                                        type="button"
                                        onClick={() => setIoTab(t)}
                                        className={[
                                          'rounded px-2 py-1 font-semibold capitalize',
                                          ioTab === t ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-50',
                                        ].join(' ')}
                                      >
                                        {t}
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>

                            {!selectedNodeId && (
                              <div className="p-3 text-sm text-gray-600">Select a node to view details.</div>
                            )}

                            {selectedNodeId && (
                              <div>
                                {(isSelectedTrigger || ioTab === 'output') && (
                                  <div className="min-w-0">
                                    <div className="border-b border-[#eceff2] bg-[#fafbfc] px-3 py-2">
                                      <span className="text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">
                                        OUTPUT
                                      </span>
                                    </div>
                                    <div className="p-3">
                                      {selectedOutputPreview?.message && (
                                        <div className="mb-2 text-sm text-amber-800">{selectedOutputPreview.message}</div>
                                      )}
                                      <NodeRunErrorDetails error={selectedRunEntry?.error} />
                                      {selectedOutputPreview ? (
                                        <IoViewer
                                          value={selectedOutputPreview.itemsJson}
                                          valueKind="executionItems"
                                          executionItemsBinaries={selectedOutputPreview.itemsBinaries}
                                          flowBlobDownloadContext={flowBlobDownloadContext}
                                          lineageCaption={selectedOutputLineage}
                                          dragSource={{
                                            nodeId: selectedNodeId,
                                            source: 'nodeOutput',
                                            nodeDisplayName: nodeLabel(nodes, selectedNodeId),
                                          }}
                                          defaultMode="schema"
                                        />
                                      ) : null}
                                    </div>
                                  </div>
                                )}

                                {!isSelectedTrigger && ioTab === 'input' && (
                                  <div className="min-w-0">
                                    <div className="border-b border-[#eceff2] bg-[#fafbfc] px-3 py-2">
                                      <span className="text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">
                                        INPUT
                                      </span>
                                    </div>
                                    <div className="p-3">
                                      {selectedParametersValue == null ? (
                                        <div className="text-sm text-gray-600">No node parameters available.</div>
                                      ) : (
                                        <IoViewer
                                          value={selectedParametersValue}
                                          valueKind="json"
                                          dragSource={{
                                            nodeId: selectedNodeId,
                                            source: 'nodeInput',
                                            nodeDisplayName: nodeLabel(nodes, selectedNodeId),
                                          }}
                                          defaultMode="schema"
                                        />
                                      )}

                                      {selectedInputPreview && (
                                        <div className="mt-4 border-t border-[#eceff2] pt-4">
                                          <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">
                                            WIRING
                                          </div>
                                          {selectedInputPreview.message ? (
                                            <div className="text-sm text-gray-600">{selectedInputPreview.message}</div>
                                          ) : (
                                            <div className="space-y-3">
                                              {selectedInputPreview.slots.map((s) => (
                                                <IoViewer
                                                  key={`${s.fromNodeId}:${s.slot}`}
                                                  title={`in ${s.slot} ← ${nodeLabel(nodes, s.fromNodeId)}`}
                                                  value={s.itemsJson}
                                                  valueKind="executionItems"
                                                  executionItemsBinaries={s.itemsBinaries}
                                                  flowBlobDownloadContext={flowBlobDownloadContext}
                                                  dragSource={{
                                                    nodeId: s.fromNodeId,
                                                    source: 'nodeOutput',
                                                    nodeDisplayName: nodeLabel(nodes, s.fromNodeId),
                                                  }}
                                                  expressionConfigNodeId={selectedNodeId}
                                                  defaultMode="schema"
                                                />
                                              ))}
                                            </div>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}

                                {selectedNodeId && ioTab === 'trace' && showTraceTab && (
                                  <div className="min-w-0">
                                    <div className="border-b border-[#eceff2] bg-[#fafbfc] px-3 py-2">
                                      <span className="text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">
                                        TRACE
                                      </span>
                                    </div>
                                    <div className="p-3">
                                      <FlowNodeTracePanel
                                        nodeError={selectedRunEntry?.error}
                                        executionError={selectedExecutionError}
                                        codeLogs={selectedOutputPreview?.logs}
                                        traceEvents={selectedRunEntry?.trace}
                                      />
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                            </div>
                          </div>
                        </Panel>
                      </PanelGroup>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default FlowLogsPanel;
