import React, { useCallback, useMemo, useRef } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
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

const FlowEditor: React.FC<{
  nodeTypes: FlowNodeType[];
  initialNodes: Node<FlowRFNodeData>[];
  initialEdges: Edge[];
  onChange: (nodes: Node<FlowRFNodeData>[], edges: Edge[], selectedNodeId: string | null) => void;
}> = ({ nodeTypes, initialNodes, initialEdges, onChange }) => {
  const nodeTypesByKey = useMemo(() => Object.fromEntries(nodeTypes.map((nt) => [nt.key, nt])), [nodeTypes]);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<FlowRFNodeData>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNodeId, setSelectedNodeId] = React.useState<string | null>(null);

  const rfNodeTypes = useMemo(
    () => ({
      'flow-node': FlowCanvasNode,
    }),
    [],
  );

  const notify = useCallback(
    (nextNodes: Node<FlowRFNodeData>[], nextEdges: Edge[], sel: string | null) => {
      onChange(nextNodes, nextEdges, sel);
    },
    [onChange],
  );

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) => {
        const next = addEdge(params, eds);
        notify(nodes, next, selectedNodeId);
        return next;
      });
    },
    [nodes, notify, selectedNodeId, setEdges],
  );

  const onSelectionChange = useCallback((e: { nodes: Node[] }) => {
    const id = e.nodes?.[0]?.id ?? null;
    setSelectedNodeId(id);
    notify(nodes, edges, id);
  }, [edges, nodes, notify]);

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
      setNodes((nds) => {
        const next = [...nds, newNode];
        notify(next, edges, selectedNodeId);
        return next;
      });
    },
    [edges, nodeTypesByKey, notify, selectedNodeId, setNodes],
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
      setNodes((nds) => {
        const next = nds.map((n) => {
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
        notify(next, edges, selectedNodeId);
        return next;
      });
    },
    [edges, nodeTypesByKey, notify, selectedNodeId, setNodes],
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
            onNodesChange={(c) => {
              onNodesChange(c);
              // best-effort: read latest state after change via callback setters
              // (ReactFlow will call state setters; we’ll notify on next render via selection changes / actions)
            }}
            onEdgesChange={(c) => {
              onEdgesChange(c);
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

