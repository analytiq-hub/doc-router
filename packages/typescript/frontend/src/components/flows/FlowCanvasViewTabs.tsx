'use client';

import React from 'react';

export type FlowCanvasView = 'editor' | 'executions';

/**
 * Centres the segmented control on the bottom edge of a `position: relative` header
 * (same pattern as n8n’s TabBar.vue: half the pill hangs below into the workspace).
 */
export function FlowWorkspaceTabStraddle({ children }: { children: React.ReactNode }) {
  return (
    <div className="pointer-events-none absolute bottom-0 left-1/2 z-30 flex min-h-[30px] -translate-x-1/2 translate-y-1/2 justify-center">
      <div className="pointer-events-auto">{children}</div>
    </div>
  );
}

/**
 * Pins nav controls to the modal’s left/right border: `inset-y-0` follows the full panel height,
 * inner `translate-x ±50%` centers the control on the stroke (same idea as {@link FlowWorkspaceTabStraddle}).
 * Render as a direct child of a `relative` modal shell so `left-0` / `right-0` match the card edge.
 */
export function FlowModalSideNavStraddle({ side, children }: { side: 'left' | 'right'; children: React.ReactNode }) {
  const inset = side === 'left' ? 'left-0' : 'right-0';
  const shift = side === 'left' ? '-translate-x-1/2' : 'translate-x-1/2';
  return (
    <div className={`pointer-events-none absolute inset-y-0 z-[50] flex items-center ${inset}`}>
      <div className={`pointer-events-auto flex flex-col items-center gap-3 ${shift}`}>{children}</div>
    </div>
  );
}

/** n8n-style pill: foreground-base track (~26px segments), rounded-md, active slice raised white. */
const FlowCanvasViewTabs: React.FC<{
  value: FlowCanvasView;
  onChange: (next: FlowCanvasView) => void;
}> = ({ value, onChange }) => {
  const segment = (active: boolean) =>
    [
      'flex h-[26px] min-w-[5rem] select-none items-center justify-center rounded-md px-3 text-[13px] font-semibold leading-none tracking-tight transition-colors',
      active
        ? 'bg-white text-gray-900 shadow-[0_1px_4px_rgba(15,23,42,0.12)]'
        : 'text-gray-600 hover:text-gray-800',
    ].join(' ');

  return (
    <div
      className="inline-flex h-auto min-h-[30px] items-center rounded-md bg-[#cdd0d5] p-[3px] shadow-[inset_0_1px_1px_rgba(15,23,42,0.07)]"
      role="tablist"
      aria-label="Flow workspace"
    >
      <button type="button" role="tab" aria-selected={value === 'editor'} onClick={() => onChange('editor')} className={segment(value === 'editor')}>
        Editor
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={value === 'executions'}
        onClick={() => onChange('executions')}
        className={segment(value === 'executions')}
      >
        Executions
      </button>
    </div>
  );
};

export default FlowCanvasViewTabs;
