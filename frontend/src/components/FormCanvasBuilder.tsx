// frontend/src/components/FormCanvasBuilder.tsx
import React, { useCallback, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  ReactFlowProvider,
  useNodesState,
  NodeTypes
} from 'reactflow';
import 'reactflow/dist/style.css';
import { FormNodeData, FormElementType } from '@/types/forms';
import FormNoteNodeComponent from '@/components/FormNoteNodeComponent';
import FormInputNodeComponent from '@/components/FormInputNodeComponent';
import FormNodePanel from '@/components/FormNodePanel';
import { nanoid } from 'nanoid'; // For unique node ids (npm install nanoid)
import FormNodeEditModal from '@/components/FormNodeEditModal';

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

const nodeTypes: NodeTypes = {
  noteNode: FormNoteNodeComponent,   // To be implemented
  inputNode: FormInputNodeComponent, // To be implemented
  // Add more as needed
};

const FormCanvasBuilder: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState<FormNodeData>(initialNodes);
  const [panelOpen, setPanelOpen] = useState(false);
  const [editNode, setEditNode] = useState<FormNodeData | null>(null);
  const [editOpen, setEditOpen] = useState(false);

  // Add node handler
  const handleAddNode = (type: string) => {
    setPanelOpen(false);
    const id = nanoid();
    const position = { x: 300, y: 200 }; // You can randomize or center
    let data: FormNodeData;
    if (type === 'note') {
      data = {
        id,
        type: 'note',
        name: 'Sticky Note',
        key: `note_${id}`,
        position,
        noteContent: 'Double click to edit me.'
      };
    } else if (type === 'text') {
      data = {
        id,
        type: 'text',
        name: 'Text Field',
        key: `text_${id}`,
        position,
        placeholder: 'Enter text...',
        required: false
      };
    }
    // Add more types as needed...

    setNodes((nds) => [
      ...nds,
      {
        id,
        type: type === 'note' ? 'noteNode' : 'inputNode',
        position,
        data
      }
    ]);
  };

  // Double-click handler
  const onNodeDoubleClick = (_: any, node: any) => {
    setEditNode(node.data);
    setEditOpen(true);
  };

  // Save handler
  const handleEditSave = (updated: FormNodeData) => {
    setNodes(nds =>
      nds.map(n =>
        n.id === updated.id
          ? { ...n, data: { ...n.data, ...updated } }
          : n
      )
    );
    setEditOpen(false);
  };

  return (
    <ReactFlowProvider>
      <div style={{ width: '100vw', height: '80vh', position: 'relative' }}>
        {/* Floating Add Button */}
        <button
          className="absolute top-4 right-4 z-50 bg-white border border-gray-300 rounded-full w-12 h-12 flex items-center justify-center shadow hover:bg-gray-100 text-2xl"
          onClick={() => setPanelOpen(true)}
          title="Open nodes panel"
        >
          +
        </button>
        <FormNodePanel isOpen={panelOpen} onAddNode={handleAddNode} onClose={() => setPanelOpen(false)} />
        <FormNodeEditModal
          node={editNode}
          isOpen={editOpen}
          onClose={() => setEditOpen(false)}
          onSave={handleEditSave}
        />
        <ReactFlow
          nodes={nodes}
          onNodesChange={onNodesChange}
          nodeTypes={nodeTypes}
          fitView
          onNodeDoubleClick={onNodeDoubleClick}
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
