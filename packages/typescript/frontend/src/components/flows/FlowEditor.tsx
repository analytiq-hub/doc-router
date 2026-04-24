import React, { useCallback, useMemo, useRef } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
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

import type { FlowNode, FlowNodeType } from '@docrouter/sdk';
import FlowNodePalette from './FlowNodePalette';
import FlowNodeConfigPanel from './FlowNodeConfigPanel';
import FlowCanvasNode from './FlowCanvasNode';
import type { FlowRFNodeData } from './flowRf';

function uuid(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : String(Date.now());
}

function parseHandleIndex(handle: string | null | undefined, prefix: string): number | null {
  if (!handle) return null;
  if (!handle.startsWith(prefix)) return null;
  const idx = Number(handle.slice(prefix.length));
  return Number.isFinite(idx) ? idx : null;
}

const FlowEditor: React.FC<{
  nodeTypes: FlowNodeType[];
  nodes: Node<FlowRFNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  onNodesChange: (next: Node<FlowRFNodeData>[]) => void;
  onEdgesChange: (next: Edge[]) => void;
  onSelectedNodeIdChange: (id: string | null) => void;
}> = ({ nodeTypes, nodes, edges, selectedNodeId, onNodesChange, onEdgesChange, onSelectedNodeIdChange }) => {
  const nodeTypesByKey = useMemo(() => Object.fromEntries(nodeTypes.map((nt) => [nt.key, nt])), [nodeTypes]);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  const rfNodeTypes = useMemo(
    () => ({
      'flow-node': FlowCanvasNode,
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

      // Validate output slot index is within declared outputs (best-effort).
      if (srcType && outIdx >= srcType.outputs) return;
      // Validate destination input index if it has a max.
      if (dstType && dstType.max_inputs != null && inIdx >= dstType.max_inputs) return;

      onEdgesChange(addEdge(params, edges));
    },
    [edges, nodeTypesByKey, nodes, onEdgesChange],
  );

  const onSelectionChange = useCallback((e: { nodes: Node[] }) => {
    const id = e.nodes?.[0]?.id ?? null;
    onSelectedNodeIdChange(id);
  }, [onSelectedNodeIdChange]);

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
      const newNode: Node<FlowRFNodeData> = {
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
    <div className="h-[calc(100vh-160px)] border border-gray-200 rounded-lg overflow-hidden">
      <div className="grid grid-cols-[260px_1fr_340px] h-full">
        <FlowNodePalette nodeTypes={nodeTypes} />
        <div ref={wrapperRef} className="h-full" onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={rfNodeTypes}
            onNodesChange={(changes: NodeChange[]) => {
              onNodesChange(applyNodeChanges(changes, nodes));
            }}
            onEdgesChange={(changes: EdgeChange[]) => {
              onEdgesChange(applyEdgeChanges(changes, edges));
            }}
            onConnect={onConnect}
            onSelectionChange={onSelectionChange}
            fitView
          >
            <Controls />
            <MiniMap />
            <Background />
          </ReactFlow>
        </div>
        <FlowNodeConfigPanel node={selected.node} nodeType={selected.nodeType} onChange={onPatchSelectedNode} />
      </div>
    </div>
  );
};

export default FlowEditor;

