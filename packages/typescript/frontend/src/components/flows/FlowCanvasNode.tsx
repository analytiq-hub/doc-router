import React from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { inputHandleCount } from './flowRf';
import type { FlowRfNodeData } from './flowRf';

const handleBase =
  'w-2.5 h-2.5 rounded-full border-2 border-white bg-blue-600';

const FlowCanvasNode: React.FC<NodeProps<FlowRfNodeData>> = ({ data, selected }) => {
  const nt = data.nodeType;
  const node = data.flowNode;

  const inputs = inputHandleCount(nt);
  const outputs = Math.max(0, nt?.outputs ?? 1);
  const outputLabels = nt?.output_labels ?? [];

  return (
    <div
      className={[
        'rounded-md border bg-white px-3 py-2 shadow-sm min-w-[180px]',
        selected ? 'border-blue-500 ring-2 ring-blue-200' : 'border-gray-200',
        node.disabled ? 'opacity-60' : '',
      ].join(' ')}
    >
      <div className="text-[11px] text-gray-500">{nt?.label ?? node.type}</div>
      <div className="text-sm font-semibold text-gray-900">{node.name}</div>

      {/* Inputs */}
      {Array.from({ length: Math.max(inputs, 0) }).map((_, i) => (
        <Handle
          key={`in-${i}`}
          id={`in-${i}`}
          type="target"
          position={Position.Left}
          className={handleBase}
          style={{ top: 40 + i * 16 }}
        />
      ))}

      {/* Outputs */}
      {Array.from({ length: Math.max(outputs, 0) }).map((_, i) => (
        <React.Fragment key={`out-${i}`}>
          <Handle
            id={`out-${i}`}
            type="source"
            position={Position.Right}
            className={handleBase}
            style={{ top: 40 + i * 16 }}
          />
          {outputLabels[i] && (
            <div
              className="absolute right-3 text-[10px] text-gray-500"
              style={{ top: 34 + i * 16 }}
            >
              {outputLabels[i]}
            </div>
          )}
        </React.Fragment>
      ))}
    </div>
  );
};

export default FlowCanvasNode;

