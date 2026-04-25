'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  getMarkerEnd,
  MarkerType,
  useReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from 'reactflow';
import { ArrowPathIcon, FunnelIcon } from '@heroicons/react/24/outline';
import 'reactflow/dist/style.css';
import type { FlowExecution, FlowNodeType } from '@docrouter/sdk';
import type { FlowRfNodeData } from './flowRf';
import { FLOW_CANVAS_GRID_PX, snapRfNodesPositions } from './canvasGrid';
import { revisionToRF } from './flowRf';
import { DocRouterOrgApi } from '@/utils/api';
import { formatLocalDate } from '@/utils/date';
import './flows-canvas.css';
import FlowCanvasNode from './FlowCanvasNode';
import FlowCanvasEdge from './FlowCanvasEdge';
import FlowNodeConfigModal from './FlowNodeConfigModal';
import { applyExecutionStatusToNodes } from './flowNodeRunStatus';

const LABELED_EDGE_TYPE = 'flowLabeled' as const;

const FLOW_EDGE_MARKER = { type: MarkerType.ArrowClosed } as const;

function toCanvasEdges(edges: Edge[]): Edge[] {
  return edges.map((e) => ({
    ...e,
    type: e.type && e.type !== 'default' ? e.type : LABELED_EDGE_TYPE,
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
}> = ({ orgApi, flowId, nodeTypes, fallbackNodes, fallbackEdges }) => {
  const nodeTypesByKey = useMemo(() => Object.fromEntries(nodeTypes.map((nt) => [nt.key, nt])), [nodeTypes]);
  const [list, setList] = useState<FlowExecution[]>([]);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState('');
  const [listLoading, setListLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [detail, setDetail] = useState<FlowExecution | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [viewNodes, setViewNodes] = useState<Node<FlowRfNodeData>[]>([]);
  const [viewEdges, setViewEdges] = useState<Edge[]>([]);
  const [configModalId, setConfigModalId] = useState<string | null>(null);
  const [fitId, setFitId] = useState('');

  const loadList = useCallback(async () => {
    try {
      setErr('');
      const res = await orgApi.listExecutions(flowId, { limit: 100, offset: 0 });
      setList(res.items);
      setTotal(res.total);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to load executions');
    } finally {
      setListLoading(false);
    }
  }, [orgApi, flowId]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const anyActive = useMemo(() => list.some(statusRunning), [list]);
  useEffect(() => {
    if (!autoRefresh || !anyActive) return;
    const n = setInterval(() => {
      void loadList();
    }, 3000);
    return () => clearInterval(n);
  }, [anyActive, autoRefresh, loadList]);

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
    if (list.length === 0 || selectedId) return;
    setSelectedId(list[0].execution_id);
  }, [list, selectedId]);

  const onNodeDoubleClick: NodeMouseHandler = useCallback((_, n) => {
    setConfigModalId(n.id);
  }, []);

  const canvasEdges = useMemo(() => toCanvasEdges(viewEdges), [viewEdges]);

  const rfNodeTypes = useMemo(() => ({ 'flow-node': FlowCanvasNode }), []);
  const rfEdgeTypes = useMemo(() => ({ [LABELED_EDGE_TYPE]: FlowCanvasEdge }), []);

  const configRf = useMemo(() => {
    const n = viewNodes.find((x) => x.id === configModalId);
    if (!n) return { node: null, nodeType: null };
    return { node: n.data.flowNode, nodeType: n.data.nodeType ?? nodeTypesByKey[n.data.flowNode.type] ?? null };
  }, [configModalId, nodeTypesByKey, viewNodes]);

  const runDataForModal = detail?.run_data as Record<string, unknown> | undefined;

  return (
    <div className="docrouter-flow-canvas flex h-[max(32rem,calc(100dvh-12.5rem))] min-h-[32rem] w-full min-w-0 flex-row overflow-hidden border-t border-[#e8eaed] bg-white">
      <aside className="flex w-[min(100%,320px)] shrink-0 flex-col border-r border-[#e8eaed] bg-[#fbfbfc]">
        <div className="flex items-center justify-between border-b border-[#eceff2] px-3 py-2">
          <span className="text-sm font-semibold text-gray-900">Executions</span>
          <div className="flex items-center gap-0.5">
            <label className="inline-flex items-center gap-1.5 text-[11px] text-gray-600">
              <input
                type="checkbox"
                className="h-3.5 w-3.5 rounded"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
              Auto refresh
            </label>
            <button
              type="button"
              className="inline-flex h-7 w-7 items-center justify-center rounded text-gray-500 hover:bg-gray-200"
              onClick={() => void loadList()}
              title="Refresh"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="h-4 w-4" />
            </button>
            <span className="inline-flex h-7 w-7 items-center justify-center text-gray-300" title="Filter (coming soon)">
              <FunnelIcon className="h-4 w-4" />
            </span>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-0">
          {err && <div className="border-b border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div>}
          {listLoading && <div className="p-3 text-sm text-gray-500">Loading…</div>}
          {!listLoading && list.length === 0 && (
            <div className="p-3 text-sm text-gray-600">No runs yet. Use <strong>Editor</strong> to execute the workflow.</div>
          )}
          <ul className="py-0">
            {list.map((e) => {
              const sel = e.execution_id === selectedId;
              return (
                <li key={e.execution_id} className="relative">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedId(e.execution_id);
                      setConfigModalId(null);
                    }}
                    className={[
                      'relative flex w-full flex-col gap-0.5 border-b border-[#e8eaed] py-2.5 pl-3 pr-2 text-left transition',
                      sel ? 'bg-gray-100' : 'bg-white hover:bg-gray-50',
                    ].join(' ')}
                  >
                    {sel && <span className="absolute left-0 top-0 h-full w-1 rounded-r bg-emerald-500" aria-hidden />}
                    <div className="pl-0.5 text-xs font-medium text-gray-500">{formatLocalDate(e.started_at)}</div>
                    <div className="pl-0.5 text-sm font-semibold text-gray-900">
                      {e.status === 'success' && 'Succeeded'}
                      {e.status === 'error' && 'Error'}
                      {e.status === 'running' && 'Running'}
                      {e.status === 'queued' && 'Queued'}
                      {e.status === 'stopped' && 'Stopped'}
                      {!['success', 'error', 'running', 'queued', 'stopped'].includes(e.status) && e.status}{' '}
                      <span className="font-normal text-gray-500">in {formatDuration(e)}</span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
        <div className="shrink-0 border-t border-[#eceff2] px-3 py-1.5 text-[10px] text-gray-400">
          {list.length} of {total} runs
        </div>
      </aside>

      <div className="relative min-h-0 min-w-0 flex-1">
        {detailLoading && (
          <div className="absolute left-0 right-0 top-0 z-20 flex h-8 items-center justify-center border-b border-amber-200/80 bg-amber-50/90 text-xs text-amber-900">
            Loading run…
          </div>
        )}
        {detail && (
          <div className="absolute left-0 right-0 top-0 z-10 border-b border-[#eceff2] bg-white/90 px-3 py-1.5 text-xs text-gray-600 backdrop-blur-sm">
            <span className="font-medium text-gray-800">{formatLocalDate(detail.started_at)}</span> · {detail.status}
            {detail.finished_at && <span> · {formatDuration(detail)}</span>} · <span className="font-mono">ID {detail.execution_id}</span>
          </div>
        )}
        {!selectedId && !listLoading && (
          <div className="absolute inset-0 z-[5] flex items-center justify-center bg-[#f7f7f9] text-sm text-gray-500">
            Select a run
          </div>
        )}

        <div className="h-full w-full min-h-0 min-w-0 bg-[#f7f7f9] pt-8">
          <ReactFlow
            className="h-full w-full"
            nodes={viewNodes as Node<FlowRfNodeData>[]}
            edges={canvasEdges}
            nodeTypes={rfNodeTypes}
            edgeTypes={rfEdgeTypes}
            nodesConnectable={false}
            elementsSelectable
            onNodeDoubleClick={onNodeDoubleClick}
            nodesDraggable={false}
            proOptions={{ hideAttribution: true }}
            minZoom={0.15}
            maxZoom={1.5}
            defaultEdgeOptions={{
              type: LABELED_EDGE_TYPE,
              style: { stroke: '#a8b0bd', strokeWidth: 1.5 },
              data: { itemCount: 1 },
                markerEnd: FLOW_EDGE_MARKER,
            }}
            fitView
            fitViewOptions={{ padding: 0.25 }}
          >
            <FitViewWhenDataChanges id={fitId} />
            <Background color="#b8c0cc" gap={FLOW_CANVAS_GRID_PX} size={1.2} variant={BackgroundVariant.Dots} />
            <Controls className="!shadow-md" position="bottom-left" showFitView showInteractive={false} />
            <MiniMap
              position="bottom-right"
              className="!m-2"
              pannable
              zoomable
              nodeStrokeWidth={2}
              maskColor="rgba(240, 240, 245, 0.7)"
            />
          </ReactFlow>
        </div>
      </div>

      <FlowNodeConfigModal
        open={configModalId != null && configRf.node != null}
        onClose={() => setConfigModalId(null)}
        readOnly
        node={configRf.node}
        nodeType={configRf.nodeType}
        edges={viewEdges}
        runData={runDataForModal}
        onChange={() => {}}
      />
    </div>
  );
};

export default FlowExecutionsView;
