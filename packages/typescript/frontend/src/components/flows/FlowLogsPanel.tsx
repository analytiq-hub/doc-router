'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { FlowExecution } from '@docrouter/sdk';
import type { Edge, Node } from 'reactflow';
import { CheckCircleIcon } from '@heroicons/react/24/solid';
import { ExclamationCircleIcon, PencilSquareIcon } from '@heroicons/react/24/outline';
import { DocRouterOrgApi } from '@/utils/api';
import { formatLocalDate } from '@/utils/date';
import { ChevronDownIcon, ChevronUpIcon, TrashIcon } from '@heroicons/react/24/outline';
import type { FlowRfNodeData } from './flowRf';
import { buildNodeInputPreview, buildNodeOutputPreview } from './flowNodeIoPreview';
import { IoViewer } from './IoViewer';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';

function isRunning(e: FlowExecution) {
  return e.status === 'queued' || e.status === 'running';
}

type LogsTab = 'overview' | 'details';

const NODE_SPLIT_STORAGE_KEY = 'docrouter.flow.logsPanel.nodeSplit.leftPct';

type RunDataEntry = {
  status?: string;
  start_time?: string;
  execution_time_ms?: number;
  data?: unknown;
  error?: unknown;
};

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
  onExecutionChange?: (e: FlowExecution | null) => void;
  onEditNode?: (nodeId: string) => void;
  expanded: boolean;
  onToggleExpanded: () => void;
  /** Current canvas graph — used for node names and input wiring in log details. */
  graphNodes?: Node<FlowRfNodeData>[];
  graphEdges?: Edge[];
}> = ({
  orgApi,
  flowId,
  focusExecutionId,
  onClearFocus,
  onExecutionChange,
  onEditNode,
  expanded,
  onToggleExpanded,
  graphNodes,
  graphEdges,
}) => {
  const [execution, setExecution] = useState<FlowExecution | null>(null);
  const [activeTab, setActiveTab] = useState<LogsTab>('overview');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [ioTab, setIoTab] = useState<'input' | 'output'>('output');
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

  const runData = execution?.run_data as Record<string, unknown> | undefined;

  const sortedRunEntries = useMemo(() => {
    if (!runData) return [];
    return Object.entries(runData)
      .map(([nodeId, raw]) => ({ nodeId, rec: raw as RunDataEntry }))
      .sort((a, b) => (a.rec.start_time ?? '').localeCompare(b.rec.start_time ?? ''));
  }, [runData]);

  useEffect(() => {
    if (!selectedNodeId && sortedRunEntries.length > 0) {
      setSelectedNodeId(sortedRunEntries[0].nodeId);
    }
  }, [selectedNodeId, sortedRunEntries]);

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
    if (isSelectedTrigger) setIoTab('output');
  }, [isSelectedTrigger]);

  const selectedRunEntry = useMemo(() => {
    if (!selectedNodeId) return null;
    const raw = runData?.[selectedNodeId];
    return raw ? (raw as RunDataEntry) : null;
  }, [runData, selectedNodeId]);

  const selectedInputPreview = useMemo(() => {
    if (!selectedNodeId) return null;
    return buildNodeInputPreview(selectedNodeId, edges, runData);
  }, [edges, runData, selectedNodeId]);

  const selectedOutputPreview = useMemo(() => {
    if (!selectedNodeId) return null;
    return buildNodeOutputPreview(selectedNodeId, runData);
  }, [runData, selectedNodeId]);

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
          {(execution || focusExecutionId) && (
            <button
              type="button"
              title="Clear execution from panel"
              onClick={onClear}
              aria-label="Clear execution"
              className="rounded-md p-1.5 text-gray-600 transition hover:bg-gray-100"
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
                {activeTab === 'overview' && (
                  <div className="mb-3 flex items-baseline justify-between gap-2 border-b border-[#eceff2] pb-2">
                    <div className="flex-none whitespace-nowrap text-sm font-semibold text-gray-900">{summaryLine}</div>
                    <div className="inline-flex flex-none rounded-md border border-gray-200 bg-white p-0.5 text-[11px]">
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
                )}

                {/* In details mode, this strip is rendered inside the left panel (next to the divider). */}

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
                            return (
                              <li key={nodeId}>
                                <div
                                  role="button"
                                  tabIndex={0}
                                  onClick={() => {
                                    setSelectedNodeId(nodeId);
                                    setActiveTab('details');
                                  }}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                      e.preventDefault();
                                      setSelectedNodeId(nodeId);
                                      setActiveTab('details');
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
                                  <div className="min-w-0 flex-1 truncate text-sm font-medium text-gray-900">{label}</div>

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
                        className="min-h-0"
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
                        <Panel defaultSize={nodeSplitLeftPct} minSize={22} className="min-w-0">
                          <div className="group relative min-w-0">
                            {/* Buttons must live inside this strip (details mode). */}
                            <div className="mb-3 flex items-baseline justify-between gap-2 border-b border-[#eceff2] pb-2 pr-2">
                              <div className="flex-none whitespace-nowrap text-sm font-semibold text-gray-900">{summaryLine}</div>
                              <div className="pointer-events-none opacity-0 transition group-hover:opacity-100">
                                <div className="pointer-events-auto inline-flex rounded-md border border-gray-200 bg-white p-0.5 text-[11px] shadow-sm">
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
                            </div>

                            <ul className="divide-y divide-[#eceff2] rounded-md border border-[#e8eaed] bg-white">
                              {sortedRunEntries.map(({ nodeId, rec }) => {
                                const ok = rec.status === 'success';
                                const label = nodeLabel(nodes, nodeId);
                                const selected = nodeId === selectedNodeId;
                                const canEdit = Boolean(onEditNode) && nodes.some((n) => n.id === nodeId);
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
                                      <div className="min-w-0 flex-1 truncate text-sm font-medium text-gray-900">
                                        {label}
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
                        <PanelResizeHandle className="w-2 cursor-col-resize bg-transparent hover:bg-[#e8eaed]" />
                        <Panel defaultSize={100 - nodeSplitLeftPct} minSize={35} className="min-w-0">
                          <div className="min-w-0">
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

                                {!isSelectedTrigger && selectedNodeId && (
                                  <div className="inline-flex shrink-0 rounded-md border border-gray-200 bg-white p-0.5 text-[11px]">
                                    {(['input', 'output'] as const).map((t) => (
                                      <button
                                        key={t}
                                        type="button"
                                        onClick={() => setIoTab(t)}
                                        className={[
                                          'rounded px-2 py-1 font-semibold',
                                          ioTab === t ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-50',
                                        ].join(' ')}
                                      >
                                        {t === 'input' ? 'Input' : 'Output'}
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
                                      {selectedOutputPreview?.data != null ? (
                                        <IoViewer
                                          value={selectedOutputPreview.data}
                                          dragSource={{ nodeId: selectedNodeId, source: 'nodeOutput' }}
                                          defaultMode="table"
                                        />
                                      ) : (
                                        !selectedOutputPreview?.message && (
                                          <div className="text-sm text-gray-600">No output payload for this node.</div>
                                        )
                                      )}
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
                                          dragSource={{ nodeId: selectedNodeId, source: 'nodeInput' }}
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
                                            <IoViewer
                                              value={
                                                selectedInputPreview.slots.length > 0
                                                  ? selectedInputPreview.slots.map((s) => ({
                                                      in: s.slot,
                                                      from: s.fromNodeId,
                                                      item: s.payload,
                                                    }))
                                                  : null
                                              }
                                              dragSource={{ nodeId: selectedNodeId, source: 'nodeInput' }}
                                              defaultMode="json"
                                            />
                                          )}
                                        </div>
                                      )}
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
