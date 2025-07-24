// frontend/src/components/FormNoteNodeComponent.tsx
import React, { useState } from 'react';
import { NodeProps } from 'reactflow';
import { FormNodeData } from '@/types/forms';

// Remove the custom props interface and use NodeProps
const FormNoteNodeComponent: React.FC<NodeProps<FormNodeData & { onDelete?: (id: string) => void }>> = ({ data, id }) => {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className="rounded-md bg-yellow-100 border border-yellow-300 p-4 min-w-[200px] min-h-[100px] shadow relative"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {hovered && (
        <button
          className="absolute top-1 right-1 bg-white border border-gray-300 rounded-full w-7 h-7 flex items-center justify-center shadow hover:bg-red-100 text-gray-500 hover:text-red-600 z-10"
          onClick={(e) => {
            e.stopPropagation();
            data.onDelete?.(id); // <-- FIX: use data.onDelete, not onDelete from props
          }}
          title="Delete note"
        >
          &times;
        </button>
      )}
      <div className="font-bold mb-1">{data.name}</div>
      <div className="text-gray-700">{data.noteContent}</div>
    </div>
  );
};

export default FormNoteNodeComponent;
