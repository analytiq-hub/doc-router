import React from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { CheckCircleIcon, CursorArrowRaysIcon, ExclamationCircleIcon, Squares2X2Icon } from '@heroicons/react/24/solid';
import { inputHandleCount } from './flowRf';
import type { FlowRfNodeDataWithRun } from './flowNodeRunStatus';

const handleClass =
  '!w-2.5 !h-2.5 -translate-y-1/2 !border-2 !border-[#d0d5dd] !bg-white hover:!border-emerald-500 hover:!bg-emerald-50';

function ExecutionStatusBadge({ status }: { status: 'success' | 'error' | 'skipped' }) {
  if (status === 'success') {
    return (
      <div
        className="pointer-events-none absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-white shadow-sm"
        title="Succeeded"
      >
        <CheckCircleIcon className="h-5 w-5 text-emerald-500" aria-hidden />
      </div>
    );
  }
  if (status === 'error') {
    return (
      <div
        className="pointer-events-none absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-white shadow-sm"
        title="Error"
      >
        <ExclamationCircleIcon className="h-5 w-5 text-red-500" aria-hidden />
      </div>
    );
  }
  return (
    <div
      className="pointer-events-none absolute -bottom-0.5 -right-0.5 h-4 min-w-4 rounded border border-amber-200 bg-amber-50 px-0.5 text-center text-[9px] font-bold leading-4 text-amber-800"
      title="Skipped"
    >
      —
    </div>
  );
}

const FlowCanvasNode: React.FC<NodeProps<FlowRfNodeDataWithRun>> = ({ data, selected }) => {
  const nt = data.nodeType;
  const node = data.flowNode;
  const isTrigger = Boolean(nt?.is_trigger);
  const runSt = data.executionNodeStatus;

  const inputs = inputHandleCount(nt);
  const outputs = Math.max(0, nt?.outputs ?? 1);
  const outputLabels = nt?.output_labels ?? [];

  const typeLabel = nt?.label ?? node.type;
  const title = node.name || typeLabel;

  if (isTrigger) {
    return (
      <div
        className={[
          'relative flex min-w-[220px] max-w-[280px] items-center gap-2 border-2 border-emerald-500/80 bg-white py-2.5 pl-3 pr-3 shadow-sm',
          'rounded-r-[32px] rounded-l-md',
          selected ? 'ring-2 ring-emerald-500/50 ring-offset-1' : '',
          node.disabled ? 'opacity-60' : '',
        ].join(' ')}
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-emerald-200 bg-gradient-to-b from-emerald-50 to-white text-emerald-600">
          <CursorArrowRaysIcon className="h-5 w-5" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-medium uppercase leading-tight tracking-wide text-emerald-800/80">
            {typeLabel}
          </div>
          <div className="line-clamp-2 text-sm font-semibold leading-tight text-gray-900" title={title}>
            {title}
          </div>
        </div>

        {Array.from({ length: Math.max(outputs, 0) }).map((_, i) => (
          <Handle
            key={`out-${i}`}
            id={`out-${i}`}
            type="source"
            position={Position.Right}
            className={handleClass}
            style={{ top: `${(100 * (i + 1)) / (outputs + 1)}%` }}
          />
        ))}
        {runSt && <ExecutionStatusBadge status={runSt} />}
      </div>
    );
  }

  return (
    <div
      className={[
        'relative min-w-[200px] max-w-[280px] rounded-2xl border-2 border-[#c8cdd5] bg-white px-3 py-2.5 shadow-sm',
        selected ? 'ring-2 ring-sky-400/70 ring-offset-1' : '',
        node.disabled ? 'opacity-60' : '',
      ].join(' ')}
    >
      {Array.from({ length: Math.max(inputs, 0) }).map((_, i) => (
        <Handle
          key={`in-${i}`}
          id={`in-${i}`}
          type="target"
          position={Position.Left}
          className={handleClass}
          style={{ top: `${(100 * (i + 1)) / (inputs + 1)}%` }}
        />
      ))}

      <div className="mb-0.5 flex items-center gap-1.5 text-[#6b6f76]">
        <Squares2X2Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="text-[10px] font-medium leading-none">{typeLabel}</span>
      </div>
      <div className="line-clamp-2 pl-0.5 text-sm font-semibold leading-tight text-[#1a1d21]">{title}</div>
      {outputLabels[0] && (
        <div className="mt-0.5 pl-0.5 text-[10px] text-[#8b9099]">Output: {outputLabels[0]}</div>
      )}

      {Array.from({ length: Math.max(outputs, 0) }).map((_, i) => (
        <React.Fragment key={`out-${i}`}>
          <Handle
            id={`out-${i}`}
            type="source"
            position={Position.Right}
            className={handleClass}
            style={{ top: `${(100 * (i + 1)) / (outputs + 1)}%` }}
          />
        </React.Fragment>
      ))}
      {runSt && <ExecutionStatusBadge status={runSt} />}
    </div>
  );
};

export default FlowCanvasNode;
