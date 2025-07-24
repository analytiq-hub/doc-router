// frontend/src/components/FormInputNodeComponent.tsx
import React from 'react';
import { NodeProps } from 'reactflow';
import { FormNodeData } from '@/types/forms';

const FormInputNodeComponent: React.FC<NodeProps<FormNodeData>> = ({ data }) => (
  <div className="rounded bg-white border p-3 min-w-[180px] shadow">
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

export default FormInputNodeComponent;



