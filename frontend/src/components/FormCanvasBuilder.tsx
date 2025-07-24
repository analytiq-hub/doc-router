// frontend/src/components/FormCanvasBuilder.tsx
import React, { useCallback, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  Node,
  Edge,
  Connection,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  NodeTypes
} from 'reactflow';
import 'reactflow/dist/style.css';
import { FormNodeData, FormElementType } from '@/types/forms';
import FormNoteNodeComponent from '@/components/FormNoteNodeComponent';
import FormInputNodeComponent from '@/components/FormInputNodeComponent';

// --- Custom node components will go here (see next steps) ---

const initialNodes: Node<FormNodeData>[] = [
  {
    id: '1',
    type: 'noteNode',
    position: { x: 100, y: 100 },
    data: {
      id: '1',
      type: 'note',
      name: "I'm a note",
      key: 'note_1',
      position: { x: 100, y: 100 },
      noteContent: 'Double click to edit me. Guide'
    }
  },
  {
    id: '2',
    type: 'inputNode',
    position: { x: 200, y: 200 },
    data: {
      id: '2',
      type: 'text',
      name: 'Insured Name',
      key: 'insured_name',
      position: { x: 200, y: 200 },
      placeholder: 'insured_full_name',
      required: true
    }
  }
];

const initialEdges: Edge[] = [];

const nodeTypes: NodeTypes = {
  noteNode: FormNoteNodeComponent,   // To be implemented
  inputNode: FormInputNodeComponent, // To be implemented
  // Add more as needed
};

const FormCanvasBuilder: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState<FormNodeData>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Add edge handler (optional, for connecting nodes)
  const onConnect = useCallback(
    (params: Edge | Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  return (
    <ReactFlowProvider>
      <div style={{ width: '100vw', height: '80vh' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          fitView
        >
          <Background />
          <MiniMap />
          <Controls />
        </ReactFlow>
      </div>
    </ReactFlowProvider>
  );
};

export default FormCanvasBuilder;
