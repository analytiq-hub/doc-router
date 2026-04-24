'use client';

import React from 'react';

export type FlowCanvasView = 'editor' | 'executions';

/** Rectangular tabs in a low track (aligns with common workflow UIs) for Editor vs execution history. */
const FlowCanvasViewTabs: React.FC<{
  value: FlowCanvasView;
  onChange: (next: FlowCanvasView) => void;
}> = ({ value, onChange }) => {
  return (
    <div className="border-b border-[#e4e4e7] bg-[#f4f4f5] px-3 py-2">
      <div className="mx-auto flex max-w-full justify-center">
        <div
          className="inline-flex items-center gap-0.5 rounded-md bg-[#d8d8dc] p-0.5 shadow-[inset_0_1px_2px_rgba(0,0,0,0.05)]"
          role="tablist"
          aria-label="Flow workspace"
        >
          <button
            type="button"
            role="tab"
            aria-selected={value === 'editor'}
            onClick={() => onChange('editor')}
            className={[
              'min-w-[7.5rem] rounded-md px-4 py-1.5 text-sm font-semibold transition',
              value === 'editor' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-800',
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
              'min-w-[7.5rem] rounded-md px-4 py-1.5 text-sm font-semibold transition',
              value === 'executions' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-800',
            ].join(' ')}
          >
            Executions
          </button>
        </div>
      </div>
    </div>
  );
};

export default FlowCanvasViewTabs;
