'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { FlowExecution } from '@docrouter/sdk';
import type { Edge, Node } from 'reactflow';
import { IconButton, Tooltip } from '@mui/material';
import { CheckCircleIcon } from '@heroicons/react/24/solid';
import { ExclamationCircleIcon } from '@heroicons/react/24/outline';
import { DocRouterOrgApi } from '@/utils/api';
import { formatLocalDate } from '@/utils/date';
import { ChevronDownIcon, ChevronUpIcon, TrashIcon } from '@heroicons/react/24/outline';
import type { FlowRfNodeData } from './flowRf';
import { buildNodeInputPreview, buildNodeOutputPreview } from './flowNodeIoPreview';

function isRunning(e: FlowExecution) {
  return e.status === 'queued' || e.status === 'running';
}

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
  /** Current canvas graph — used for node names and input wiring in log details. */
  graphNodes?: Node<FlowRfNodeData>[];
  graphEdges?: Edge[];
}> = ({ orgApi, flowId, focusExecutionId, onClearFocus, onExecutionChange, graphNodes, graphEdges }) => {
  const [expanded, setExpanded] = useState(false);
  const [execution, setExecution] = useState<FlowExecution | null>(null);
  const [detailsNodeId, setDetailsNodeId] = useState<string | null>(null);

  const edges = graphEdges ?? [];
  const nodes = graphNodes ?? [];

  useEffect(() => {
    if (focusExecutionId) {
      setExpanded(true);
    }
  }, [focusExecutionId]);

  useEffect(() => {
    onExecutionChange?.(execution);
  }, [execution, onExecutionChange]);

  useEffect(() => {
    setDetailsNodeId(null);
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
    setDetailsNodeId(null);
    setErr('');
  };

  const runData = execution?.run_data as Record<string, unknown> | undefined;

  const sortedRunEntries = useMemo(() => {
    if (!runData) return [];
    return Object.entries(runData)
      .map(([nodeId, raw]) => ({ nodeId, rec: raw as RunDataEntry }))
      .sort((a, b) => (a.rec.start_time ?? '').localeCompare(b.rec.start_time ?? ''));
  }, [runData]);

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

  return (
    <div className="shrink-0 border-t border-[#e2e4e8] bg-[#fbfbfc]" data-testid="flow-logs-panel">
      <div className="flex h-11 items-center justify-between gap-2 px-3">
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
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
            <Tooltip title="Clear execution from panel">
              <IconButton size="small" onClick={onClear} aria-label="Clear execution">
                <TrashIcon className="h-4 w-4" />
              </IconButton>
            </Tooltip>
          )}
          <IconButton size="small" onClick={() => setExpanded((e) => !e)} aria-label={expanded ? 'Collapse' : 'Expand'}>
            {expanded ? <ChevronDownIcon className="h-5 w-5" /> : <ChevronUpIcon className="h-5 w-5" />}
          </IconButton>
        </div>
      </div>
      {expanded && (
        <div className="max-h-[min(50vh,560px)] overflow-auto border-t border-[#eceff2] bg-white">
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
                <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2 border-b border-[#eceff2] pb-2">
                  <div className="text-sm font-semibold text-gray-900">{summaryLine}</div>
                  <div className="text-[11px] text-gray-500">
                    {execution.mode && <span className="mr-2">Mode: {execution.mode}</span>}
                    <span className="font-mono">ID {execution.execution_id}</span>
                  </div>
                </div>

                {sortedRunEntries.length === 0 ? (
                  <div className="text-sm text-gray-600">No node results recorded yet for this run.</div>
                ) : (
                  <ul className="divide-y divide-[#eceff2] rounded-md border border-[#e8eaed]">
                    {sortedRunEntries.map(({ nodeId, rec }) => {
                      const ok = rec.status === 'success';
                      const label = nodeLabel(nodes, nodeId);
                      const open = detailsNodeId === nodeId;
                      const inputPreview = buildNodeInputPreview(nodeId, edges, runData);
                      const outputPreview = buildNodeOutputPreview(nodeId, runData);
                      return (
                        <li key={nodeId} className="bg-white">
                          <div className="flex items-center gap-2 px-2 py-2 sm:px-3">
                            <div className="shrink-0">
                              {ok ? (
                                <CheckCircleIcon className="h-5 w-5 text-emerald-500" aria-hidden />
                              ) : (
                                <ExclamationCircleIcon className="h-5 w-5 text-red-500" aria-hidden />
                              )}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-sm font-medium text-gray-900">{label}</div>
                              <div className="text-xs text-gray-500">
                                {rec.status ?? '—'} · {formatExecutionMs(rec.execution_time_ms)}
                                {rec.start_time && (
                                  <span className="ml-1">· started {formatLocalDate(rec.start_time)}</span>
                                )}
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() => setDetailsNodeId(open ? null : nodeId)}
                              className="shrink-0 rounded border border-[#d8dce3] bg-white px-2.5 py-1 text-xs font-semibold text-gray-700 shadow-sm hover:bg-gray-50"
                            >
                              {open ? 'Hide' : 'Details'}
                            </button>
                          </div>
                          {open && (
                            <div className="grid gap-0 border-t border-[#eceff2] bg-[#fafbfc] sm:grid-cols-2">
                              <div className="min-w-0 border-[#e8eaed] sm:border-r">
                                <div className="border-b border-[#eceff2] bg-[#f4f5f6] px-2 py-1.5">
                                  <span className="text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">
                                    Input
                                  </span>
                                </div>
                                <div className="max-h-64 overflow-auto p-2">
                                  {inputPreview.message && (
                                    <div className="mb-2 text-xs text-gray-600">{inputPreview.message}</div>
                                  )}
                                  {!inputPreview.message && inputPreview.slots.length > 0 && (
                                    <pre className="whitespace-pre-wrap break-words font-mono text-[11px] leading-relaxed text-gray-800">
                                      {JSON.stringify(
                                        inputPreview.slots.map((s) => ({
                                          in: s.slot,
                                          from: s.fromNodeId,
                                          item: s.payload,
                                        })),
                                        null,
                                        2,
                                      )}
                                    </pre>
                                  )}
                                </div>
                              </div>
                              <div className="min-w-0">
                                <div className="border-b border-[#eceff2] bg-[#f4f5f6] px-2 py-1.5">
                                  <span className="text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">
                                    Output
                                  </span>
                                </div>
                                <div className="max-h-64 overflow-auto p-2">
                                  {outputPreview.message && (
                                    <div className="mb-2 text-xs text-amber-800">{outputPreview.message}</div>
                                  )}
                                  {outputPreview.data != null ? (
                                    <pre className="whitespace-pre-wrap break-words font-mono text-[11px] leading-relaxed text-gray-800">
                                      {JSON.stringify(outputPreview.data, null, 2)}
                                    </pre>
                                  ) : (
                                    !outputPreview.message && (
                                      <div className="text-xs text-gray-500">No output payload for this node.</div>
                                    )
                                  )}
                                </div>
                              </div>
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
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
