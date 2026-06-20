'use client';

import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  Panel as RFPanel,
  useReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from 'reactflow';
import { ArrowPathIcon } from '@heroicons/react/24/outline';
import 'reactflow/dist/style.css';
import type { FlowExecution, FlowNodeType } from '@docrouter/sdk';
import type { FlowRfNodeData } from './flowRf';
import { FLOW_CANVAS_GRID_PX, snapRfNodesPositions } from './canvasGrid';
import { edgesWithRunDataItemCounts } from './flowNodeIoPreview';
import { revisionToRF } from './flowRf';
import { DocRouterOrgApi } from '@/utils/api';
import { formatLocalDate } from '@/utils/date';
import './flows-canvas.css';
import { FLOW_RF_LABELED_EDGE_TYPE } from './flowRfCanvasTypes';
import { useStableFlowRfCanvasRegistration } from './useStableFlowRfCanvasRegistration';
import { FLOW_RF_PANEL_CLEAR_BELOW_WORKSPACE_TABS } from './flowUiClasses';
import FlowLogsPanel from './FlowLogsPanel';
import type { FlowExecutionBlobContext } from './flowExecutionBlob';
import FlowNodeConfigModal from './FlowNodeConfigModal';
import { applyExecutionStatusToNodes } from './flowNodeRunStatus';
import { Panel, PanelGroup, PanelResizeHandle, type ImperativePanelGroupHandle } from 'react-resizable-panels';

const FLOW_EDGE_MARKER = { type: MarkerType.ArrowClosed } as const;

/** SSR + initial client paint: must equal server HTML so hydrated nodes match panels. Persisted ratio is reapplied after mount via `PanelGroup#setLayout`. */
const EXECUTIONS_LIST_PANEL_DEFAULT_PCT = 30;

const RF_EXEC_VIEW_DEFAULT_EDGE_OPTIONS = {
  type: FLOW_RF_LABELED_EDGE_TYPE,
  style: { stroke: '#a8b0bd', strokeWidth: 1.5 },
  markerEnd: FLOW_EDGE_MARKER,
} as const;

const RF_EXEC_VIEW_PRO_OPTIONS = { hideAttribution: true } as const;
const RF_EXEC_VIEW_FIT_OPTIONS = { padding: 0.2, maxZoom: 1 } as const;

const EXECUTIONS_LIST_SPLIT_STORAGE_KEY = 'docrouter.flow.executionsView.listLeftPct';

const EXEC_LOGS_COLLAPSED_PCT = 8;
const EXEC_LOGS_MIN_EXPANDED_PCT = EXEC_LOGS_COLLAPSED_PCT;
const EXEC_LOGS_MAX_EXPANDED_PCT = 90;
const EXEC_LOGS_EXPANDED_STORAGE_KEY = 'docrouter.flow.executionsView.logsPanel.expandedPct';

/** Read persisted list width (client-only; do not call during SSR / first paint). */
function readStoredExecutionsListLeftPct(): number {
  if (typeof window === 'undefined') return EXECUTIONS_LIST_PANEL_DEFAULT_PCT;
  try {
    const raw = window.localStorage.getItem(EXECUTIONS_LIST_SPLIT_STORAGE_KEY);
    const n = raw ? Number(raw) : NaN;
    if (!Number.isFinite(n)) return EXECUTIONS_LIST_PANEL_DEFAULT_PCT;
    // One-time bump: old default was 22%; widen for status line layout without clearing storage.
    if (raw != null && (raw === '22' || raw === '22.0')) {
      const next = EXECUTIONS_LIST_PANEL_DEFAULT_PCT;
      window.localStorage.setItem(EXECUTIONS_LIST_SPLIT_STORAGE_KEY, String(next));
      return next;
    }
    return Math.min(52, Math.max(18, n));
  } catch {
    return EXECUTIONS_LIST_PANEL_DEFAULT_PCT;
  }
}

function toCanvasEdges(edges: Edge[]): Edge[] {
  return edges.map((e) => ({
    ...e,
    type: e.type && e.type !== 'default' ? e.type : FLOW_RF_LABELED_EDGE_TYPE,
    markerEnd: e.markerEnd ?? FLOW_EDGE_MARKER,
  }));
}

function statusRunning(e: FlowExecution) {
  return e.status === 'queued' || e.status === 'running';
}

function formatDuration(e: FlowExecution) {
  const end = e.finished_at ? new Date(e.finished_at).getTime() : Date.now();
  const start = new Date(e.started_at).getTime();
  if (!Number.isFinite(end) || !Number.isFinite(start)) return '—';
  const s = Math.max(0, Math.round((end - start) / 1000));
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function FitViewWhenDataChanges({ id }: { id: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    if (!id) return;
    const t = window.setTimeout(() => {
      void fitView({ padding: 0.25, maxZoom: 1 });
    }, 50);
    return () => clearTimeout(t);
  }, [fitView, id]);
  return null;
}

const FlowExecutionsView: React.FC<{
  orgApi: DocRouterOrgApi;
  flowId: string;
  nodeTypes: FlowNodeType[];
  /** Latest graph from the editor; used if an execution’s revision is unavailable. */
  fallbackNodes: Node<FlowRfNodeData>[];
  fallbackEdges: Edge[];
  /** Open editor and focus node config — e.g. from logs “Edit node”. */
  onEditFlowNode?: (nodeId: string) => void;
  /** When true, omit top border (workspace header above already divides the pane). */
  suppressTopChrome?: boolean;
}> = ({ orgApi, flowId, nodeTypes, fallbackNodes, fallbackEdges, onEditFlowNode, suppressTopChrome }) => {
  const { rfCanvasNodeTypes, rfCanvasEdgeTypes } = useStableFlowRfCanvasRegistration();
  const nodeTypesByKey = useMemo(() => Object.fromEntries(nodeTypes.map((nt) => [nt.key, nt])), [nodeTypes]);
  const [list, setList] = useState<FlowExecution[]>([]);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState('');
  const [listLoading, setListLoading] = useState(true);
  const [listPagination, setListPagination] = useState({ page: 0, pageSize: 20 });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<FlowExecution | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [stopLoadingId, setStopLoadingId] = useState<string | null>(null);
  const userClearedSelectionRef = useRef(false);
  const [viewNodes, setViewNodes] = useState<Node<FlowRfNodeData>[]>([]);
  const [viewEdges, setViewEdges] = useState<Edge[]>([]);
  const [configModalId, setConfigModalId] = useState<string | null>(null);
  const [fitId, setFitId] = useState('');
  const executionsSplitRef = useRef<ImperativePanelGroupHandle | null>(null);
  const execLogsPanelGroupRef = useRef<ImperativePanelGroupHandle | null>(null);
  const [execLogsExpanded, setExecLogsExpanded] = useState(false);
  const [execLogsExpandedPct, setExecLogsExpandedPct] = useState<number>(() => {
    if (typeof window === 'undefined') return 50;
    try {
      const raw = window.localStorage.getItem(EXEC_LOGS_EXPANDED_STORAGE_KEY);
      const n = raw ? Number(raw) : NaN;
      if (!Number.isFinite(n)) return 50;
      return Math.min(EXEC_LOGS_MAX_EXPANDED_PCT, Math.max(EXEC_LOGS_MIN_EXPANDED_PCT, n));
    } catch {
      return 50;
    }
  });

  const applyExecLogsLayout = useCallback(
    (nextExpanded: boolean, nextExpandedPct?: number) => {
      const api = execLogsPanelGroupRef.current;
      if (!api) return;
      if (!nextExpanded) {
        api.setLayout([100 - EXEC_LOGS_COLLAPSED_PCT, EXEC_LOGS_COLLAPSED_PCT]);
        return;
      }
      const pct = Math.min(
        EXEC_LOGS_MAX_EXPANDED_PCT,
        Math.max(EXEC_LOGS_MIN_EXPANDED_PCT, nextExpandedPct ?? execLogsExpandedPct),
      );
      api.setLayout([100 - pct, pct]);
    },
    [execLogsExpandedPct],
  );

  const toggleExecLogsExpanded = useCallback(() => {
    setExecLogsExpanded((cur) => {
      const next = !cur;
      queueMicrotask(() => applyExecLogsLayout(next));
      return next;
    });
  }, [applyExecLogsLayout]);

  /** Reconcile client with localStorage after hydration so SSR % matches first paint HTML. */
  useLayoutEffect(() => {
    const left = readStoredExecutionsListLeftPct();
    executionsSplitRef.current?.setLayout([left, 100 - left]);
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setExecLogsExpanded(true);
    queueMicrotask(() => applyExecLogsLayout(true));
  }, [applyExecLogsLayout, selectedId]);

  const loadList = useCallback(async () => {
    try {
      setListLoading(true);
      setErr('');
      const res = await orgApi.listExecutions({
        flowId,
        limit: listPagination.pageSize,
        offset: listPagination.page * listPagination.pageSize,
      });
      setList(res.items);
      setTotal(res.total);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to load executions');
    } finally {
      setListLoading(false);
    }
  }, [orgApi, flowId, listPagination.page, listPagination.pageSize]);

  useLayoutEffect(() => {
    setListPagination({ page: 0, pageSize: 20 });
  }, [flowId]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const loadDetailAndGraph = useCallback(
    async (id: string) => {
      setDetailLoading(true);
      try {
        setErr('');
        const ex = await orgApi.getExecution(flowId, id);
        setDetail(ex);
        const runData = ex.run_data as Record<string, unknown> | undefined;
        if (ex.flow_revid) {
          try {
            const rev = await orgApi.getRevision(flowId, ex.flow_revid);
            const { nodes, edges } = revisionToRF(rev, nodeTypesByKey);
            const snapped = snapRfNodesPositions(nodes as Node<FlowRfNodeData>[]);
            setViewNodes(applyExecutionStatusToNodes(snapped, runData) as Node<FlowRfNodeData>[]);
            setViewEdges(toCanvasEdges(edges as Edge[]));
            setFitId(`${id}-${ex.flow_revid}`);
            return;
          } catch {
            // fall through to fallback graph
          }
        }
        setViewNodes(
          applyExecutionStatusToNodes(snapRfNodesPositions(fallbackNodes), runData) as Node<FlowRfNodeData>[],
        );
        setViewEdges(toCanvasEdges(fallbackEdges));
        setFitId(`${id}-fallback`);
      } catch (e: unknown) {
        setErr(e instanceof Error ? e.message : 'Failed to load execution');
        setDetail(null);
      } finally {
        setDetailLoading(false);
      }
    },
    [fallbackEdges, fallbackNodes, flowId, nodeTypesByKey, orgApi],
  );

  const clearFocus = useCallback(() => {
    userClearedSelectionRef.current = true;
    setSelectedId(null);
  }, []);

  const onExecutionDeleted = useCallback(
    (executionId: string) => {
      setList((prev) => {
        const next = prev.filter((e) => e.execution_id !== executionId);
        setSelectedId((cur) => {
          if (cur !== executionId) return cur;
          userClearedSelectionRef.current = next.length === 0;
          return next[0]?.execution_id ?? null;
        });
        return next;
      });
      setTotal((t) => Math.max(0, t - 1));
      void loadList();
    },
    [loadList],
  );
  const stopExecution = useCallback(
    async (executionId: string) => {
      try {
        setErr('');
        setStopLoadingId(executionId);
        await orgApi.stopExecution(flowId, executionId);
        await loadList();
        if (selectedId === executionId) {
          await loadDetailAndGraph(executionId);
        }
      } catch (e: unknown) {
        setErr(e instanceof Error ? e.message : 'Failed to stop execution');
      } finally {
        setStopLoadingId(null);
      }
    },
    [flowId, loadDetailAndGraph, loadList, orgApi, selectedId],
  );

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setViewNodes([]);
      setViewEdges([]);
      setConfigModalId(null);
      return;
    }
    void loadDetailAndGraph(selectedId);
  }, [loadDetailAndGraph, selectedId]);

  useEffect(() => {
    if (list.length === 0) return;
    if (selectedId && list.some((e) => e.execution_id === selectedId)) return;
    if (selectedId && !list.some((e) => e.execution_id === selectedId)) {
      userClearedSelectionRef.current = false;
      setSelectedId(list[0].execution_id);
      return;
    }
    if (!selectedId && !userClearedSelectionRef.current) {
      setSelectedId(list[0].execution_id);
    }
  }, [list, selectedId]);

  const onNodeDoubleClick: NodeMouseHandler = useCallback((_, n) => {
    setConfigModalId(n.id);
  }, []);

  const runDataForEdges = detail?.run_data as Record<string, unknown> | undefined;
  const canvasEdges = useMemo(
    () => edgesWithRunDataItemCounts(toCanvasEdges(viewEdges), runDataForEdges),
    [viewEdges, runDataForEdges],
  );

  const configRf = useMemo(() => {
    const n = viewNodes.find((x) => x.id === configModalId);
    if (!n) return { node: null, nodeType: null };
    return { node: n.data.flowNode, nodeType: nodeTypesByKey[n.data.flowNode.type] ?? n.data.nodeType ?? null };
  }, [configModalId, nodeTypesByKey, viewNodes]);

  const runDataForModal = detail?.run_data as Record<string, unknown> | undefined;
  const listPageCount = Math.max(1, Math.ceil(total / listPagination.pageSize));

  return (
    <div
      className={[
        'docrouter-flow-canvas flex h-full min-h-0 w-full min-w-0 flex-1 overflow-hidden bg-white',
        suppressTopChrome ? '' : 'border-t border-[#e8eaed]',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <PanelGroup
        ref={executionsSplitRef}
        direction="horizontal"
        className="flex min-h-0 min-w-0 flex-1"
        onLayout={(sizes) => {
          const left = sizes[0];
          if (typeof left !== 'number' || !Number.isFinite(left)) return;
          try {
            window.localStorage.setItem(EXECUTIONS_LIST_SPLIT_STORAGE_KEY, String(Math.round(left * 10) / 10));
          } catch {
            /* ignore */
          }
        }}
      >
        <Panel defaultSize={EXECUTIONS_LIST_PANEL_DEFAULT_PCT} minSize={18} maxSize={52} className="min-h-0 min-w-0">
          <aside className="flex h-full w-full flex-col border-r border-[#e8eaed] bg-[#fbfbfc]">
        <div className="flex items-center justify-between border-b border-[#eceff2] px-3 py-2">
          <span className="text-sm font-semibold text-gray-900">Executions</span>
          <div className="flex items-center gap-0.5">
            <button
              type="button"
              className="inline-flex h-7 w-7 items-center justify-center rounded text-gray-500 hover:bg-gray-200"
              onClick={() => void loadList()}
              title="Refresh"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-0">
          {err && <div className="border-b border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div>}
          {listLoading && <div className="p-3 text-sm text-gray-500">Loading…</div>}
          {!listLoading && list.length === 0 && total === 0 && (
            <div className="p-3 text-sm text-gray-600">No runs yet. Use <strong>Editor</strong> to execute the workflow.</div>
          )}
          <ul className="py-0">
            {list.map((e) => {
              const sel = e.execution_id === selectedId;
              const running = statusRunning(e);
              const stopping = stopLoadingId === e.execution_id;
              return (
                <li key={e.execution_id} className="relative">
                  <div
                    className={[
                      'relative flex w-full items-stretch gap-1 border-b border-[#e8eaed] text-left transition',
                      sel ? 'bg-gray-100' : 'bg-white hover:bg-gray-50',
                    ].join(' ')}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        userClearedSelectionRef.current = false;
                        setSelectedId(e.execution_id);
                        setConfigModalId(null);
                      }}
                      className="relative flex min-w-0 flex-1 flex-col gap-0.5 py-2.5 pl-3 pr-2"
                    >
                      {sel && (
                        <span className="absolute left-0 top-0 h-full w-1 rounded-r bg-emerald-500" aria-hidden />
                      )}
                      <div className="pl-0.5 text-xs font-medium text-gray-500">{formatLocalDate(e.started_at)}</div>
                      <div
                        className="block min-w-0 pl-0.5 text-sm font-semibold leading-snug text-gray-900 overflow-hidden text-ellipsis whitespace-nowrap text-left"
                        title={
                          `${e.status === 'success' ? 'Succeeded' : e.status === 'error' ? 'Error' : e.status === 'running' ? 'Running' : e.status === 'queued' ? 'Queued' : e.status === 'stopped' ? 'Stopped' : e.status} in ${formatDuration(e)}`
                        }
                      >
                        {e.status === 'success' && 'Succeeded'}
                        {e.status === 'error' && 'Error'}
                        {e.status === 'running' && 'Running'}
                        {e.status === 'queued' && 'Queued'}
                        {e.status === 'stopped' && 'Stopped'}
                        {!['success', 'error', 'running', 'queued', 'stopped'].includes(e.status) && e.status}{' '}
                        <span className="font-normal text-gray-500">in {formatDuration(e)}</span>
                      </div>
                    </button>

                    {running && (
                      <div className="flex shrink-0 flex-col justify-center pr-2">
                        <button
                          type="button"
                          disabled={stopping}
                          onClick={(ev) => {
                            ev.preventDefault();
                            ev.stopPropagation();
                            void stopExecution(e.execution_id);
                          }}
                          className={[
                            'rounded border px-2.5 py-1 text-xs font-semibold shadow-sm transition',
                            stopping
                              ? 'cursor-not-allowed border-gray-200 bg-gray-100 text-gray-400'
                              : 'border-red-200 bg-white text-red-700 hover:bg-red-50',
                          ].join(' ')}
                          title="Request stop"
                          aria-label="Stop execution"
                        >
                          {stopping ? 'Stopping…' : 'Stop'}
                        </button>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-1 border-t border-[#eceff2] px-2 py-1.5 text-[10px] text-gray-500">
          <span className="min-w-0 truncate">
            {total} run{total === 1 ? '' : 's'} · p.{listPagination.page + 1}/{listPageCount}
          </span>
          <div className="flex shrink-0 items-center gap-0.5">
            <button
              type="button"
              className="rounded border border-gray-200 bg-white px-1 py-0.5 text-[10px] font-medium disabled:opacity-40"
              disabled={listPagination.page <= 0}
              onClick={() => setListPagination((p) => ({ ...p, page: Math.max(0, p.page - 1) }))}
              title="Previous page"
            >
              ‹
            </button>
            <button
              type="button"
              className="rounded border border-gray-200 bg-white px-1 py-0.5 text-[10px] font-medium disabled:opacity-40"
              disabled={listPagination.page >= listPageCount - 1}
              onClick={() =>
                setListPagination((p) => ({ ...p, page: Math.min(listPageCount - 1, p.page + 1) }))
              }
              title="Next page"
            >
              ›
            </button>
          </div>
        </div>
          </aside>
        </Panel>

        <PanelResizeHandle className="w-2 shrink-0 cursor-col-resize bg-transparent hover:bg-[#e8eaed]" />

        <Panel
          defaultSize={100 - EXECUTIONS_LIST_PANEL_DEFAULT_PCT}
          minSize={38}
          className="flex min-h-0 min-w-0 flex-col"
        >
          <PanelGroup
            ref={execLogsPanelGroupRef}
            direction="vertical"
            className="flex min-h-0 min-w-0 flex-1 flex-col"
            onLayout={(sizes) => {
              const bottom = sizes[1] ?? 0;
              if (bottom <= EXEC_LOGS_COLLAPSED_PCT + 0.5) {
                if (execLogsExpanded) setExecLogsExpanded(false);
                return;
              }
              if (!execLogsExpanded) setExecLogsExpanded(true);
              const next = Math.min(EXEC_LOGS_MAX_EXPANDED_PCT, Math.max(EXEC_LOGS_MIN_EXPANDED_PCT, bottom));
              setExecLogsExpandedPct(next);
              try {
                window.localStorage.setItem(EXEC_LOGS_EXPANDED_STORAGE_KEY, String(next));
              } catch {
                // ignore
              }
            }}
          >
            <Panel defaultSize={100 - EXEC_LOGS_COLLAPSED_PCT} minSize={25} className="min-h-0 min-w-0">
              <div className="relative flex h-full min-h-0 min-w-0 flex-col bg-[#f7f7f9]">
                {!selectedId && !listLoading && (
                  <div className="pointer-events-none absolute inset-0 z-[5] flex items-center justify-center bg-[#f7f7f9] text-sm text-gray-500">
                    Select a run
                  </div>
                )}
                <ReactFlow
                  className="h-full w-full flex-1 min-h-0"
                  nodes={viewNodes as Node<FlowRfNodeData>[]}
                  edges={canvasEdges}
                  nodeTypes={rfCanvasNodeTypes}
                  edgeTypes={rfCanvasEdgeTypes}
                  nodesConnectable={false}
                  elementsSelectable
                  onNodeDoubleClick={onNodeDoubleClick}
                  nodesDraggable={false}
                  proOptions={RF_EXEC_VIEW_PRO_OPTIONS}
                  minZoom={0.15}
                  maxZoom={1.5}
                  defaultEdgeOptions={RF_EXEC_VIEW_DEFAULT_EDGE_OPTIONS}
                  fitView
                  fitViewOptions={RF_EXEC_VIEW_FIT_OPTIONS}
                >
                  {selectedId && detailLoading ? (
                    <RFPanel
                      position="top-left"
                      className={`!z-[30] !left-0 !right-0 !top-0 !m-0 !w-auto rounded-none border-0 border-b border-amber-200/80 bg-amber-50 px-3 !pb-1.5 text-center text-xs text-amber-900 ${FLOW_RF_PANEL_CLEAR_BELOW_WORKSPACE_TABS}`}
                    >
                      Loading run…
                    </RFPanel>
                  ) : null}
                  {selectedId && !detailLoading && detail ? (
                    <RFPanel
                      position="top-left"
                      className={`!z-[30] !left-0 !right-0 !top-0 !m-0 !max-w-none !w-auto rounded-none border-0 bg-[#f7f7f9] px-3 !pb-1.5 text-xs text-gray-600 shadow-none ${FLOW_RF_PANEL_CLEAR_BELOW_WORKSPACE_TABS}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="m-0 min-w-0 leading-snug break-words">
                          <span className="font-medium text-gray-800">{formatLocalDate(detail.started_at)}</span> · {detail.status}
                          {detail.finished_at && <span> · {formatDuration(detail)}</span>} ·{' '}
                          <span className="font-mono text-[11px] text-gray-700">ID {detail.execution_id}</span>
                        </p>
                        <div className="flex shrink-0 items-center gap-0.5 self-start pt-px">
                          {statusRunning(detail) && (
                            <button
                              type="button"
                              disabled={stopLoadingId === detail.execution_id}
                              onClick={(ev) => {
                                ev.preventDefault();
                                ev.stopPropagation();
                                void stopExecution(detail.execution_id);
                              }}
                              className={[
                                'shrink-0 rounded border px-2.5 py-1 text-[11px] font-semibold shadow-sm transition',
                                stopLoadingId === detail.execution_id
                                  ? 'cursor-not-allowed border-gray-200 bg-gray-100 text-gray-400'
                                  : 'border-red-200 bg-white text-red-700 hover:bg-red-50',
                              ].join(' ')}
                              title="Request stop"
                              aria-label="Stop execution"
                            >
                              {stopLoadingId === detail.execution_id ? 'Stopping…' : 'Stop'}
                            </button>
                          )}
                        </div>
                      </div>
                    </RFPanel>
                  ) : null}
                  <FitViewWhenDataChanges id={fitId} />
                  <Background color="#b8c0cc" gap={FLOW_CANVAS_GRID_PX} size={1.2} variant={BackgroundVariant.Dots} />
                  <Controls className="!shadow-md" position="bottom-left" showFitView showInteractive={false} />
                </ReactFlow>
              </div>
            </Panel>
            {execLogsExpanded ? (
              <PanelResizeHandle className="h-2 cursor-row-resize shrink-0 bg-[#e8eaed] hover:bg-[#d8dde4]" />
            ) : (
              <PanelResizeHandle className="h-px shrink-0 bg-[#e8eaed]" />
            )}
            <Panel defaultSize={EXEC_LOGS_COLLAPSED_PCT} minSize={EXEC_LOGS_COLLAPSED_PCT} className="min-h-0 min-w-0">
              <div className="h-full min-h-0 min-w-0">
                <FlowLogsPanel
                  orgApi={orgApi}
                  flowId={flowId}
                  focusExecutionId={selectedId}
                  onClearFocus={clearFocus}
                  onExecutionDeleted={onExecutionDeleted}
                  onEditNode={onEditFlowNode}
                  expanded={execLogsExpanded}
                  onToggleExpanded={toggleExecLogsExpanded}
                  graphNodes={viewNodes}
                  graphEdges={viewEdges}
                />
              </div>
            </Panel>
          </PanelGroup>
        </Panel>
      </PanelGroup>

      <FlowNodeConfigModal
        open={configModalId != null && configRf.node != null}
        onClose={() => setConfigModalId(null)}
        readOnly
        flowOrgApi={orgApi}
        node={configRf.node}
        nodeType={configRf.nodeType}
        allNodes={viewNodes.map((n) => (n as Node<FlowRfNodeData>).data.flowNode)}
        nodeTypes={nodeTypes}
        edges={viewEdges}
        runData={runDataForModal}
        expressionExecution={
          detail
            ? {
                execution_id: detail.execution_id,
                flow_id: detail.flow_id,
                flow_revid: detail.flow_revid,
              }
            : null
        }
        executionError={
          detail?.status === 'error' &&
          detail.last_node_executed === configModalId &&
          detail.error &&
          typeof detail.error === 'object'
            ? detail.error
            : null
        }
        flowBlobDownloadContext={
          detail?.execution_id && detail.flow_id
            ? ({
                organizationId: orgApi.organizationId,
                flowId: detail.flow_id,
                executionId: detail.execution_id,
              } satisfies FlowExecutionBlobContext)
            : null
        }
        onSelectNode={(nodeId) => setConfigModalId(nodeId)}
        onChange={() => {}}
      />
    </div>
  );
};

export default FlowExecutionsView;
