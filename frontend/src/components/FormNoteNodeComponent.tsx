// frontend/src/components/FormNoteNodeComponent.tsx
import React from 'react';
import { NodeProps } from 'reactflow';
import { FormNodeData } from '@/types/forms';

const FormNoteNodeComponent: React.FC<NodeProps<FormNodeData>> = ({ data }) => (
  <div className="rounded-md bg-yellow-100 border border-yellow-300 p-4 min-w-[200px] min-h-[100px] shadow">
    <div className="font-bold mb-1">{data.name}</div>
    <div className="text-gray-700">{data.noteContent}</div>
  </div>
);

export default FormNoteNodeComponent;
