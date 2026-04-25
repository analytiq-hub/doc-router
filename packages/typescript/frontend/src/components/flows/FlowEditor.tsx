'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  Panel,
  addEdge,
  getNodesBounds,
  getViewportForBounds,
  getMarkerEnd,
  MarkerType,
  useNodesInitialized,
  useReactFlow,
  useStore,
  type Connection,
  type Edge,
  type Node,
  applyEdgeChanges,
  applyNodeChanges,
  type EdgeChange,
  type NodeChange,
} from 'reactflow';
import {
  ArrowUturnLeftIcon,
  ArrowsPointingOutIcon,
  BeakerIcon,
  MagnifyingGlassIcon,
  MagnifyingGlassMinusIcon,
  MagnifyingGlassPlusIcon,
  PlusIcon,
  Square2StackIcon,
} from '@heroicons/react/24/outline';
import { XMarkIcon } from '@heroicons/react/24/solid';
import 'reactflow/dist/style.css';
import './flows-canvas.css';

import type { FlowExecution, FlowNode, FlowNodeType } from '@docrouter/sdk';
import FlowNodePalette from './FlowNodePalette';
import FlowNodeConfigModal from './FlowNodeConfigModal';
import { FLOW_RF_LABELED_EDGE_TYPE, flowRfEdgeTypes, flowRfNodeTypes } from './flowRfCanvasTypes';
import {
  FlowCanvasActionsProvider,
  FlowExecutionVisualProvider,
  type EdgeInsertPayload,
} from './flowCanvasActionsContext';
import { FLOW_CANVAS_GRID_PX, snapToFlowGrid } from './canvasGrid';
import { inputHandleCount } from './flowRf';
import type { FlowRfNodeData } from './flowRf';

const EXECUTE_BUTTON_BG = '#ff6d5a';
const EXECUTE_BUTTON_BG_HOVER = '#e85d4d';

const FLOW_EDGE_MARKER = { type: MarkerType.ArrowClosed } as const;

function CanvasZoomControls({ addFooterPadding }: { addFooterPadding: boolean }) {
  const { setViewport, getNodes, zoomIn, zoomOut, zoomTo } = useReactFlow();
  const nodesInitialized = useNodesInitialized();
  const width = useStore((s) => s.width);
  const height = useStore((s) => s.height);
  const didInitialFitRef = useRef(false);

  const onZoomToFit = useCallback(async () => {
    const nodes = getNodes().filter((n) => !n.hidden);
    if (!nodes.length || width === 0 || height === 0) return;

    // Reserve space for bottom UI controls when fitting.
    const footerHeightPx = addFooterPadding ? 200 : 100;
    const bounds = getNodesBounds(nodes);
    const next = getViewportForBounds(bounds, width, Math.max(1, height - footerHeightPx), 0.15, 1, 0.2);
    await setViewport(next, { duration: 200 });
  }, [addFooterPadding, getNodes, height, setViewport, width]);

  useEffect(() => {
    if (!nodesInitialized) return;
    if (didInitialFitRef.current) return;
    didInitialFitRef.current = true;
    void onZoomToFit();
  }, [nodesInitialized, onZoomToFit]);

  return (
    <Panel position="bottom-left" className="!mb-3 !ml-3 flex items-center gap-1 rounded-lg bg-white/95 p-1 shadow-md backdrop-blur-sm">
      <button
        type="button"
        onClick={() => void onZoomToFit()}
        title="Zoom to fit"
        aria-label="Zoom to fit"
        className="rounded-md p-1.5 text-gray-700 transition hover:bg-gray-100"
      >
        <ArrowsPointingOutIcon className="h-5 w-5" />
      </button>
      <button
        type="button"
        onClick={() => void zoomIn({ duration: 120 })}
        title="Zoom in"
        aria-label="Zoom in"
        className="rounded-md p-1.5 text-gray-700 transition hover:bg-gray-100"
      >
        <MagnifyingGlassPlusIcon className="h-5 w-5" />
      </button>
      <button
        type="button"
        onClick={() => void zoomOut({ duration: 120 })}
        title="Zoom out"
        aria-label="Zoom out"
        className="rounded-md p-1.5 text-gray-700 transition hover:bg-gray-100"
      >
        <MagnifyingGlassMinusIcon className="h-5 w-5" />
      </button>
      <button
        type="button"
        onClick={() => void zoomTo(1, { duration: 120 })}
        title="Reset zoom"
        aria-label="Reset zoom"
        className="rounded-md p-1.5 text-gray-700 transition hover:bg-gray-100"
      >
        <ArrowUturnLeftIcon className="h-5 w-5" />
      </button>
    </Panel>
  );
}

function escapeRegexLiteral(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function makeUniqueNodeName(base: string, existingNames: string[]): string {
  const trimmed = base.trim();
  const safeBase = trimmed.length ? trimmed : 'Node';
  const set = new Set(existingNames.map((n) => n.trim()).filter(Boolean));
  if (!set.has(safeBase)) return safeBase;

  const re = new RegExp(`^${escapeRegexLiteral(safeBase)}(?:\\s+(\\d+))?$`);
  let maxSuffix = 0;
  for (const n of set) {
    const m = re.exec(n);
    if (!m) continue;
    const suffix = m[1] ? Number(m[1]) : 0;
    if (Number.isFinite(suffix) && suffix > maxSuffix) maxSuffix = suffix;
  }
  return `${safeBase} ${maxSuffix + 1}`;
}

function uuid(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : String(Date.now());
}

function parseHandleIndex(handle: string | null | undefined, prefix: string): number | null {
  if (!handle) return null;
  if (!handle.startsWith(prefix)) return null;
  const idx = Number(handle.slice(prefix.length));
  return Number.isFinite(idx) ? idx : null;
}

function toCanvasEdges(edges: Edge[]): Edge[] {
  return edges.map((e) => ({
    ...e,
    type: e.type && e.type !== 'default' ? e.type : FLOW_RF_LABELED_EDGE_TYPE,
    markerEnd: e.markerEnd ?? FLOW_EDGE_MARKER,
  }));
}

/** Lives inside `<ReactFlow>`; forwards `screenToFlowPosition` to a ref for drop / palette placement. */
function ScreenToFlowPointBridge({
  targetRef,
}: {
  targetRef: React.MutableRefObject<((p: { x: number; y: number }) => { x: number; y: number }) | null>;
}) {
  const { screenToFlowPosition } = useReactFlow();
  useEffect(() => {
    targetRef.current = screenToFlowPosition;
  }, [screenToFlowPosition, targetRef]);
  return null;
}

const FlowEditor: React.FC<{
  nodeTypes: FlowNodeType[];
  nodes: Node<FlowRfNodeData>[];
  edges: Edge[];
  onNodesChange: (next: Node<FlowRfNodeData>[]) => void;
  onEdgesChange: (next: Edge[]) => void;
  onExecute?: () => void;
  /** Latest execution to drive Input / Output columns in the node modal (e.g. from logs panel). */
  executionForIo?: FlowExecution | null;
}> = ({ nodeTypes, nodes, edges, onNodesChange, onEdgesChange, onExecute, executionForIo }) => {
  const [nodePaletteOpen, setNodePaletteOpen] = useState(false);
  const [configModalNodeId, setConfigModalNodeId] = useState<string | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const nodeTypesByKey = useMemo(() => Object.fromEntries(nodeTypes.map((nt) => [nt.key, nt])), [nodeTypes]);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const screenToFlowPointRef = useRef<((p: { x: number; y: number }) => { x: number; y: number }) | null>(null);
  const pendingEdgeInsertRef = useRef<EdgeInsertPayload | null>(null);
  const canvasEdges = useMemo(() => toCanvasEdges(edges), [edges]);
  const runData = executionForIo?.run_data as Record<string, unknown> | undefined;

  useEffect(() => {
    if (configModalNodeId && !nodes.some((n) => n.id === configModalNodeId)) {
      setConfigModalNodeId(null);
    }
  }, [configModalNodeId, nodes]);

  useEffect(() => {
    if (nodePaletteOpen) {
      const t = window.setTimeout(() => searchInputRef.current?.focus(), 100);
      return () => clearTimeout(t);
    }
  }, [nodePaletteOpen]);

  const closePalette = useCallback(() => {
    pendingEdgeInsertRef.current = null;
    setNodePaletteOpen(false);
  }, []);

  const openPalette = useCallback(() => {
    pendingEdgeInsertRef.current = null;
    setNodePaletteOpen(true);
  }, []);

  useEffect(() => {
    if (!nodePaletteOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closePalette();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [nodePaletteOpen, closePalette]);

  const onConnect = useCallback(
    (params: Connection) => {
      const outIdx = parseHandleIndex(params.sourceHandle, 'out-');
      const inIdx = parseHandleIndex(params.targetHandle, 'in-');
      if (outIdx == null || inIdx == null) return;

      const src = nodes.find((n) => n.id === params.source);
      const dst = nodes.find((n) => n.id === params.target);
      const srcType = src ? nodeTypesByKey[src.data.flowNode.type] : undefined;
      const dstType = dst ? nodeTypesByKey[dst.data.flowNode.type] : undefined;

      if (outIdx < 0 || (srcType && outIdx >= (srcType.outputs ?? 0))) return;
      const maxIn = inputHandleCount(dstType);
      if (inIdx < 0 || inIdx >= maxIn) return;

      onEdgesChange(
        addEdge(
          {
            ...params,
            type: FLOW_RF_LABELED_EDGE_TYPE,
            style: { stroke: '#a8b0bd', strokeWidth: 1.5 },
            data: { itemCount: 1 },
            markerEnd: FLOW_EDGE_MARKER,
          },
          edges,
        ),
      );
    },
    [edges, nodeTypesByKey, nodes, onEdgesChange],
  );

  const onNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodesChange(nodes.map((n) => (n.id === node.id ? { ...n, selected: true } : { ...n, selected: false })));
      setConfigModalNodeId(node.id);
    },
    [nodes, onNodesChange],
  );

  const onPatchNodeById = useCallback(
    (id: string, patch: Partial<FlowNode>) => {
      if (!id) return;
      const next = nodes.map((n) => {
        if (n.id !== id) return n;
        const flowNode = { ...n.data.flowNode, ...patch, parameters: patch.parameters ?? n.data.flowNode.parameters };
        return {
          ...n,
          data: {
            ...n.data,
            flowNode,
            nodeType: n.data.nodeType ?? nodeTypesByKey[flowNode.type],
          },
        };
      });
      onNodesChange(next);
    },
    [nodeTypesByKey, nodes, onNodesChange],
  );

  const insertNodeOnSplitEdge = useCallback(
    (pending: EdgeInsertPayload, typeKey: string): boolean => {
      const nt = nodeTypesByKey[typeKey];
      if (!nt) return false;
      if (inputHandleCount(nt) < 1 || (nt.outputs ?? 0) < 1) return false;

      if (!edges.some((e) => e.id === pending.edgeId)) return false;

      const srcNode = nodes.find((n) => n.id === pending.source);
      const dstNode = nodes.find((n) => n.id === pending.target);
      if (!srcNode?.data.flowNode || !dstNode?.data.flowNode) return false;

      const sh = pending.sourceHandle ?? 'out-0';
      const th = pending.targetHandle ?? 'in-0';
      const outIdx = parseHandleIndex(sh, 'out-');
      const inIdx = parseHandleIndex(th, 'in-');
      if (outIdx == null || inIdx == null) return false;

      const srcType = srcNode.data.nodeType ?? nodeTypesByKey[srcNode.data.flowNode.type];
      const dstType = dstNode.data.nodeType ?? nodeTypesByKey[dstNode.data.flowNode.type];
      if (outIdx < 0 || (srcType && outIdx >= (srcType.outputs ?? 0))) return false;
      if (inIdx < 0 || inIdx >= inputHandleCount(dstType)) return false;

      const newId = uuid();
      const pos = snapToFlowGrid({ x: pending.flowPosition.x, y: pending.flowPosition.y });
      const baseName = nt.label ? `${nt.label}` : typeKey;
      const uniqueName = makeUniqueNodeName(
        baseName,
        nodes.map((n) => n.data.flowNode.name),
      );
      const flowNode: FlowNode = {
        id: newId,
        name: uniqueName,
        type: typeKey,
        position: [pos.x, pos.y],
        parameters: {},
        disabled: false,
        on_error: 'stop',
        notes: null,
      };
      const newNode: Node<FlowRfNodeData> = {
        id: newId,
        type: 'flow-node',
        position: pos,
        selected: true,
        data: { flowNode, nodeType: nt },
      };

      const rest = edges.filter((e) => e.id !== pending.edgeId);
      const edgeBase = {
        type: FLOW_RF_LABELED_EDGE_TYPE,
        style: { stroke: '#a8b0bd', strokeWidth: 1.5 } as const,
        data: { itemCount: 1 },
        markerEnd: FLOW_EDGE_MARKER,
      };
      const e1: Edge = {
        id: uuid(),
        source: pending.source,
        target: newId,
        sourceHandle: sh,
        targetHandle: 'in-0',
        ...edgeBase,
      };
      const e2: Edge = {
        id: uuid(),
        source: newId,
        target: pending.target,
        sourceHandle: 'out-0',
        targetHandle: th,
        ...edgeBase,
      };

      onNodesChange([...nodes.map((n) => ({ ...n, selected: false })), newNode]);
      onEdgesChange([...rest, e1, e2]);
      setConfigModalNodeId(newId);
      return true;
    },
    [edges, nodeTypesByKey, nodes, onEdgesChange, onNodesChange],
  );

  const addNodeFromTypeAtViewCenter = useCallback(
    (typeKey: string) => {
      const pending = pendingEdgeInsertRef.current;
      if (pending) {
        pendingEdgeInsertRef.current = null;
        const ok = insertNodeOnSplitEdge(pending, typeKey);
        if (ok) {
          closePalette();
          return;
        }
        pendingEdgeInsertRef.current = pending;
        return;
      }

      const stf = screenToFlowPointRef.current;
      const el = wrapperRef.current;
      if (!stf || !el) return;

      const r = el.getBoundingClientRect();
      const p = snapToFlowGrid(stf({ x: r.left + r.width / 2, y: r.top + r.height / 2 }));
      const nt = nodeTypesByKey[typeKey];
      const id = uuid();
      const baseName = nt?.label ? `${nt.label}` : typeKey;
      const uniqueName = makeUniqueNodeName(
        baseName,
        nodes.map((n) => n.data.flowNode.name),
      );
      const flowNode: FlowNode = {
        id,
        name: uniqueName,
        type: typeKey,
        position: [p.x, p.y],
        parameters: {},
        disabled: false,
        on_error: 'stop',
        notes: null,
      };
      const newNode: Node<FlowRfNodeData> = {
        id,
        type: 'flow-node',
        position: p,
        selected: true,
        data: { flowNode, nodeType: nt },
      };
      onNodesChange([...nodes.map((n) => ({ ...n, selected: false })), newNode]);
      setConfigModalNodeId(id);
      closePalette();
    },
    [closePalette, insertNodeOnSplitEdge, nodeTypesByKey, nodes, onNodesChange],
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      pendingEdgeInsertRef.current = null;
      const typeKey = event.dataTransfer.getData('application/flow-node-type');
      if (!typeKey) return;

      const stf = screenToFlowPointRef.current;
      if (!stf) return;
      const p = snapToFlowGrid(stf({ x: event.clientX, y: event.clientY }));
      const nt = nodeTypesByKey[typeKey];
      const id = uuid();
      const baseName = nt?.label ? `${nt.label}` : typeKey;
      const uniqueName = makeUniqueNodeName(
        baseName,
        nodes.map((n) => n.data.flowNode.name),
      );
      const flowNode: FlowNode = {
        id,
        name: uniqueName,
        type: typeKey,
        position: [p.x, p.y],
        parameters: {},
        disabled: false,
        on_error: 'stop',
        notes: null,
      };
      const newNode: Node<FlowRfNodeData> = {
        id,
        type: 'flow-node',
        position: p,
        data: { flowNode, nodeType: nt },
      };
      onNodesChange([...nodes, newNode]);
    },
    [nodeTypesByKey, nodes, onNodesChange],
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const configRf = useMemo(() => {
    const n = nodes.find((x) => x.id === configModalNodeId);
    if (!n) return { node: null as FlowNode | null, nodeType: null as FlowNodeType | null };
    return { node: n.data.flowNode, nodeType: n.data.nodeType ?? nodeTypesByKey[n.data.flowNode.type] ?? null };
  }, [configModalNodeId, nodeTypesByKey, nodes]);

  const canvasActions = useMemo(
    () => ({
      onRunWorkflow: onExecute,
      onToggleNodeDisabled: (nodeId: string) => {
        onNodesChange(
          nodes.map((n) => {
            if (n.id !== nodeId) return n;
            const fn = n.data.flowNode;
            return {
              ...n,
              data: {
                ...n.data,
                flowNode: { ...fn, disabled: !fn.disabled },
                nodeType: n.data.nodeType ?? nodeTypesByKey[fn.type],
              },
            };
          }),
        );
      },
      onDeleteNode: (nodeId: string) => {
        onNodesChange(nodes.filter((n) => n.id !== nodeId));
        onEdgesChange(edges.filter((e) => e.source !== nodeId && e.target !== nodeId));
      },
      onOpenNodeSettings: (nodeId: string) => {
        onNodesChange(nodes.map((n) => ({ ...n, selected: n.id === nodeId })));
        setConfigModalNodeId(nodeId);
      },
      onDeleteEdge: (edgeId: string) => {
        onEdgesChange(edges.filter((e) => e.id !== edgeId));
      },
      onBeginInsertOnEdge: (payload: EdgeInsertPayload) => {
        pendingEdgeInsertRef.current = payload;
        setNodePaletteOpen(true);
      },
    }),
    [edges, nodeTypesByKey, nodes, onEdgesChange, onExecute, onNodesChange],
  );

  return (
    <div className="docrouter-flow-canvas flex h-full min-h-[20rem] w-full min-w-0 flex-col overflow-hidden rounded-lg border border-[#e2e4e8] bg-[#f7f7f9]">
      <div ref={wrapperRef} className="relative h-full min-h-[12rem] min-w-0" onDrop={onDrop} onDragOver={onDragOver}>
        <FlowCanvasActionsProvider value={canvasActions}>
          <FlowExecutionVisualProvider execution={executionForIo}>
            <ReactFlow
              className="h-full w-full"
              nodes={nodes}
              edges={canvasEdges}
              nodeTypes={flowRfNodeTypes}
              edgeTypes={flowRfEdgeTypes}
              onNodesChange={(changes: NodeChange[]) => {
                onNodesChange(applyNodeChanges(changes, nodes));
              }}
              onEdgesChange={(changes: EdgeChange[]) => {
                onEdgesChange(applyEdgeChanges(changes, edges));
              }}
              onConnect={onConnect}
              onNodeDoubleClick={onNodeDoubleClick}
              snapToGrid
              snapGrid={[FLOW_CANVAS_GRID_PX, FLOW_CANVAS_GRID_PX]}
              proOptions={{ hideAttribution: true }}
              minZoom={0.15}
              maxZoom={1.5}
              defaultEdgeOptions={{
                type: FLOW_RF_LABELED_EDGE_TYPE,
                style: { stroke: '#a8b0bd', strokeWidth: 1.5 },
                data: { itemCount: 1 },
                markerEnd: FLOW_EDGE_MARKER,
              }}
              connectionLineStyle={{ stroke: '#94a3b8', strokeWidth: 1.5 }}
              elevateEdgesOnSelect
            >
              <ScreenToFlowPointBridge targetRef={screenToFlowPointRef} />
              <Background color="#b8c0cc" gap={FLOW_CANVAS_GRID_PX} size={1.2} variant={BackgroundVariant.Dots} />
              <Controls className="!shadow-md" position="bottom-left" showZoom={false} showFitView={false} showInteractive={false} />
              <CanvasZoomControls addFooterPadding={Boolean(onExecute)} />
              {onExecute && (
                <Panel position="bottom-center" className="!mb-6">
                  <button
                    type="button"
                    onClick={onExecute}
                    className="inline-flex items-center gap-2 rounded-md px-5 py-2.5 text-sm font-semibold text-white shadow-md transition hover:opacity-95 active:scale-[0.99]"
                    style={{ backgroundColor: EXECUTE_BUTTON_BG }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.backgroundColor = EXECUTE_BUTTON_BG_HOVER;
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.backgroundColor = EXECUTE_BUTTON_BG;
                    }}
                  >
                    <BeakerIcon className="h-4 w-4" aria-hidden />
                    Execute workflow
                  </button>
                </Panel>
              )}
            </ReactFlow>
          </FlowExecutionVisualProvider>
        </FlowCanvasActionsProvider>

        {nodes.length === 0 && (
          <div className="pointer-events-none absolute inset-0 z-[5] flex items-center justify-center">
            <button
              type="button"
              onClick={openPalette}
              className="pointer-events-auto flex h-[100px] w-[100px] flex-col items-center justify-center rounded-xl border-2 border-dashed border-[#b8c0cc] bg-white/90 px-2 text-center text-sm font-semibold text-[#5a6270] shadow-sm transition hover:border-sky-400 hover:text-sky-800"
            >
              Add first step
            </button>
          </div>
        )}

        <div className="pointer-events-auto absolute right-2 top-1/2 z-10 flex -translate-y-1/2 flex-col gap-0.5 rounded-lg border border-[#d8dde4] bg-white/95 p-0.5 shadow-md backdrop-blur-sm">
          <button
            type="button"
            onClick={openPalette}
            title="Add node"
            aria-label="Add node"
            className="rounded-md p-1.5 text-gray-700 transition hover:bg-gray-100"
          >
            <PlusIcon className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={openPalette}
            title="Search nodes"
            aria-label="Search nodes"
            className="rounded-md p-1.5 text-gray-700 transition hover:bg-gray-100"
          >
            <MagnifyingGlassIcon className="h-5 w-5" />
          </button>
          <button
            type="button"
            disabled
            title="Coming soon"
            aria-label="Duplicate (coming soon)"
            className="cursor-not-allowed rounded-md p-1.5 text-gray-400"
          >
            <Square2StackIcon className="h-5 w-5" />
          </button>
        </div>
      </div>

      <FlowNodeConfigModal
        open={configModalNodeId != null && configRf.node != null}
        onClose={() => setConfigModalNodeId(null)}
        node={configRf.node}
        nodeType={configRf.nodeType}
        allNodes={nodes.map((n) => n.data.flowNode)}
        edges={edges}
        runData={runData}
        onSelectNode={(nodeId) => {
          onNodesChange(nodes.map((n) => ({ ...n, selected: n.id === nodeId })));
          setConfigModalNodeId(nodeId);
        }}
        onChange={(patch) => {
          if (configModalNodeId) onPatchNodeById(configModalNodeId, patch);
        }}
      />

      {nodePaletteOpen && (
        <>
          <div className="fixed inset-0 z-[150] bg-black/20" onClick={closePalette} aria-hidden />
          <div
            className="fixed right-0 top-0 z-[160] flex h-full w-[min(100vw,300px)] min-w-0 flex-col border-l border-[#e2e4e8] bg-white shadow-xl"
            role="dialog"
            aria-modal
            aria-label="Add node"
          >
            <div className="flex items-center justify-between border-b border-[#eceff2] px-3 py-2">
              <span className="text-sm font-semibold text-gray-900">Add node</span>
              <button
                type="button"
                onClick={closePalette}
                aria-label="Close"
                className="rounded-md p-1.5 text-gray-600 transition hover:bg-gray-100"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="min-h-0 flex-1">
              <FlowNodePalette
                nodeTypes={nodeTypes}
                embedInDrawer
                searchInputRef={searchInputRef}
                onNodeTypeDoubleClick={addNodeFromTypeAtViewCenter}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default FlowEditor;
