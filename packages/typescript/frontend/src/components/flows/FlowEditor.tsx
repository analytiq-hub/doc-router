import React, { useCallback, useMemo, useRef } from 'react';
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Panel,
  addEdge,
  type Connection,
  type Edge,
  type Node,
  applyEdgeChanges,
  applyNodeChanges,
  type EdgeChange,
  type NodeChange,
} from 'reactflow';
import 'reactflow/dist/style.css';
import './flows-canvas.css';

import type { FlowNode, FlowNodeType } from '@docrouter/sdk';
import FlowNodePalette from './FlowNodePalette';
import FlowNodeConfigPanel from './FlowNodeConfigPanel';
import FlowCanvasNode from './FlowCanvasNode';
import FlowCanvasEdge from './FlowCanvasEdge';
import { inputHandleCount } from './flowRf';
import type { FlowRfNodeData } from './flowRf';

const EXECUTE_BUTTON_BG = '#ff6d5a';
const EXECUTE_BUTTON_BG_HOVER = '#e85d4d';

/** React Flow `edgeTypes` key for the smooth step edge with item-count label. */
const LABELED_EDGE_TYPE = 'flowLabeled' as const;

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
    type: e.type && e.type !== 'default' ? e.type : LABELED_EDGE_TYPE,
  }));
}

const FlowEditor: React.FC<{
  nodeTypes: FlowNodeType[];
  nodes: Node<FlowRfNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  onNodesChange: (next: Node<FlowRfNodeData>[]) => void;
  onEdgesChange: (next: Edge[]) => void;
  onSelectedNodeIdChange: (id: string | null) => void;
  /** Primary “run workflow” action shown on the canvas (optional). */
  onExecute?: () => void;
}> = ({
  nodeTypes,
  nodes,
  edges,
  selectedNodeId,
  onNodesChange,
  onEdgesChange,
  onSelectedNodeIdChange,
  onExecute,
}) => {
  const nodeTypesByKey = useMemo(() => Object.fromEntries(nodeTypes.map((nt) => [nt.key, nt])), [nodeTypes]);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const canvasEdges = useMemo(() => toCanvasEdges(edges), [edges]);

  const rfNodeTypes = useMemo(
    () => ({
      'flow-node': FlowCanvasNode,
    }),
    [],
  );

  const rfEdgeTypes = useMemo(
    () => ({
      [LABELED_EDGE_TYPE]: FlowCanvasEdge,
    }),
    [],
  );

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
            type: LABELED_EDGE_TYPE,
            style: { stroke: '#a8b0bd', strokeWidth: 1.5 },
            data: { itemCount: 1 },
          },
          edges,
        ),
      );
    },
    [edges, nodeTypesByKey, nodes, onEdgesChange],
  );

  const onSelectionChange = useCallback(
    (e: { nodes: Node[] }) => {
      const id = e.nodes?.[0]?.id ?? null;
      onSelectedNodeIdChange(id);
    },
    [onSelectedNodeIdChange],
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const typeKey = event.dataTransfer.getData('application/flow-node-type');
      if (!typeKey) return;

      const bounds = wrapperRef.current?.getBoundingClientRect();
      const position = bounds
        ? { x: event.clientX - bounds.left, y: event.clientY - bounds.top }
        : { x: event.clientX, y: event.clientY };

      const nt = nodeTypesByKey[typeKey];
      const id = uuid();
      const flowNode: FlowNode = {
        id,
        name: nt?.label ? `${nt.label}` : typeKey,
        type: typeKey,
        position: [Math.round(position.x), Math.round(position.y)],
        parameters: {},
        disabled: false,
        on_error: 'stop',
        notes: null,
      };
      const newNode: Node<FlowRfNodeData> = {
        id,
        type: 'flow-node',
        position,
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

  const selected = useMemo(() => {
    const n = nodes.find((x) => x.id === selectedNodeId);
    if (!n) return { node: null as FlowNode | null, nodeType: null as FlowNodeType | null };
    return { node: n.data.flowNode, nodeType: n.data.nodeType ?? nodeTypesByKey[n.data.flowNode.type] ?? null };
  }, [nodeTypesByKey, nodes, selectedNodeId]);

  const onPatchSelectedNode = useCallback(
    (patch: Partial<FlowNode>) => {
      if (!selectedNodeId) return;
      const next = nodes.map((n) => {
        if (n.id !== selectedNodeId) return n;
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
    [nodeTypesByKey, nodes, onNodesChange, selectedNodeId],
  );

  return (
    <div className="docrouter-flow-canvas h-[min(80vh,calc(100vh-10rem))] min-h-[480px] overflow-hidden rounded-lg border border-[#e2e4e8] bg-[#f7f7f9]">
      <div className="grid h-full w-full [grid-template-columns:minmax(200px,240px)_1fr_minmax(300px,380px)]">
        <FlowNodePalette nodeTypes={nodeTypes} />
        <div
          ref={wrapperRef}
          className="relative h-full min-h-0"
          onDrop={onDrop}
          onDragOver={onDragOver}
        >
          <ReactFlow
            className="h-full w-full"
            nodes={nodes}
            edges={canvasEdges}
            nodeTypes={rfNodeTypes}
            edgeTypes={rfEdgeTypes}
            onNodesChange={(changes: NodeChange[]) => {
              onNodesChange(applyNodeChanges(changes, nodes));
            }}
            onEdgesChange={(changes: EdgeChange[]) => {
              onEdgesChange(applyEdgeChanges(changes, edges));
            }}
            onConnect={onConnect}
            onSelectionChange={onSelectionChange}
            fitView
            fitViewOptions={{ padding: 0.25 }}
            proOptions={{ hideAttribution: true }}
            minZoom={0.15}
            maxZoom={1.5}
            defaultEdgeOptions={{
              type: LABELED_EDGE_TYPE,
              style: { stroke: '#a8b0bd', strokeWidth: 1.5 },
              data: { itemCount: 1 },
            }}
            connectionLineStyle={{ stroke: '#94a3b8', strokeWidth: 1.5 }}
            elevateEdgesOnSelect
          >
            <Background color="#b8c0cc" gap={20} size={1.2} variant={BackgroundVariant.Dots} />
            <Controls
              className="!shadow-md"
              position="bottom-left"
              showFitView
              showInteractive={false}
            />
            <MiniMap
              position="bottom-right"
              className="!m-2"
              pannable
              zoomable
              nodeStrokeWidth={2}
              maskColor="rgba(240, 240, 245, 0.7)"
            />
            {onExecute && (
              <Panel position="bottom-center" className="!mb-2">
                <button
                  type="button"
                  onClick={onExecute}
                  className="rounded-md px-6 py-2.5 text-sm font-semibold text-white shadow-md transition hover:opacity-95 active:scale-[0.99]"
                  style={{ backgroundColor: EXECUTE_BUTTON_BG }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.backgroundColor = EXECUTE_BUTTON_BG_HOVER;
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.backgroundColor = EXECUTE_BUTTON_BG;
                  }}
                >
                  Execute workflow
                </button>
              </Panel>
            )}
          </ReactFlow>
        </div>
        <FlowNodeConfigPanel node={selected.node} nodeType={selected.nodeType} onChange={onPatchSelectedNode} />
      </div>
    </div>
  );
};

export default FlowEditor;
