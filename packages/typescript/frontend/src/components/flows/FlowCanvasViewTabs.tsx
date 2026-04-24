'use client';

import React from 'react';

export type FlowCanvasView = 'editor' | 'executions';

/** Segmented control for the main flow workspace (Editor vs execution history). */
const FlowCanvasViewTabs: React.FC<{
  value: FlowCanvasView;
  onChange: (next: FlowCanvasView) => void;
}> = ({ value, onChange }) => {
  return (
    <div className="flex justify-center border-b border-[#e8eaed] bg-[#fbfbfc] py-2.5">
      <div
        className="inline-flex rounded-full bg-[#e3e5e8] p-1 shadow-[inset_0_1px_2px_rgba(0,0,0,0.06)]"
        role="tablist"
        aria-label="Flow workspace"
      >
        <button
          type="button"
          role="tab"
          aria-selected={value === 'editor'}
          onClick={() => onChange('editor')}
          className={[
            'min-w-[8rem] rounded-full px-5 py-2 text-sm font-semibold transition',
            value === 'editor'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-600 hover:text-gray-800',
          ].join(' ')}
        >
          Editor
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={value === 'executions'}
          onClick={() => onChange('executions')}
          className={[
            'min-w-[8rem] rounded-full px-5 py-2 text-sm font-semibold transition',
            value === 'executions'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-600 hover:text-gray-800',
          ].join(' ')}
        >
          Executions
        </button>
      </div>
    </div>
  );
};

export default FlowCanvasViewTabs;
