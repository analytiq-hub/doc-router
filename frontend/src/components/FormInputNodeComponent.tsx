// frontend/src/components/FormInputNodeComponent.tsx
import React, { useState } from 'react';
import { NodeProps } from 'reactflow';
import { FormNodeData } from '@/types/forms';

const FormInputNodeComponent: React.FC<NodeProps<FormNodeData & { onDelete?: (id: string) => void }>> = ({ data, id }) => {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className="rounded bg-white border p-3 min-w-[180px] shadow relative"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {hovered && (
        <button
          className="absolute top-1 right-1 bg-white border border-gray-300 rounded-full w-7 h-7 flex items-center justify-center shadow hover:bg-red-100 text-gray-500 hover:text-red-600 z-10"
          onClick={(e) => {
            e.stopPropagation();
            data.onDelete?.(id);
          }}
          title="Delete node"
        >
          &times;
        </button>
      )}
      <label className="block font-semibold mb-1">
        {data.name}
        {data.required && <span className="text-red-500">*</span>}
      </label>
      <input
        className="w-full border rounded px-2 py-1"
        placeholder={data.placeholder}
        required={data.required}
        type="text"
      />
    </div>
  );
};

export default FormInputNodeComponent;



