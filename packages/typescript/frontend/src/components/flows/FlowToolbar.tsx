'use client';

import React, { useState } from 'react';
import FlowStatusBadge from './FlowStatusBadge';
import { flowInlineNameInputClass, flowInlineNameMeasureClass, flowInlineNameReadClass } from './flowUiClasses';
import { useInlineNameWidthPx } from './useInlineNameWidthPx';

const flowToolbarBtnClass =
  'inline-flex items-center justify-center rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-800 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50';
const runBtnClass =
  'inline-flex items-center justify-center rounded-md px-4 py-1.5 text-sm font-semibold text-white shadow-sm transition hover:opacity-95 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50';

const FlowToolbar: React.FC<{
  name: string;
  onNameChange: (name: string) => void;
  active: boolean;
  isDirty: boolean;
  isSaving: boolean;
  onSave: () => void;
  onRun: () => void;
  onActivate: () => void;
  onDeactivate: () => void;
}> = ({ name, onNameChange, active, isDirty, isSaving, onSave, onRun, onActivate, onDeactivate }) => {
  const [nameHover, setNameHover] = useState(false);
  const [nameFocus, setNameFocus] = useState(false);
  const showNameField = nameHover || nameFocus;
  const measure = useInlineNameWidthPx(name, 'Flow name');

  return (
    <div className="flex items-center justify-between border-b border-gray-200 bg-white px-3 py-2">
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1 pr-2">
        <div
          className="max-w-full shrink-0"
          onMouseEnter={() => setNameHover(true)}
          onMouseLeave={() => setNameHover(false)}
        >
          <span
            ref={measure.spanRef}
            className={flowInlineNameMeasureClass}
            style={{
              position: 'absolute',
              visibility: 'hidden',
              pointerEvents: 'none',
              whiteSpace: 'pre',
            }}
            aria-hidden
          >
            {measure.basis}
          </span>
          {showNameField ? (
            <input
              className={flowInlineNameInputClass}
              style={measure.widthPx ? { width: `${measure.widthPx}px` } : undefined}
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              placeholder="Flow name"
              aria-label="Flow name"
              onFocus={() => setNameFocus(true)}
              onBlur={() => setNameFocus(false)}
            />
          ) : (
            <span className={flowInlineNameReadClass} title={name || 'Flow name'}>
              {name.trim() ? name : 'Untitled flow'}
            </span>
          )}
        </div>
        <FlowStatusBadge active={active} />
        {isDirty && <div className="shrink-0 text-xs text-amber-700">Unsaved changes</div>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <button type="button" className={flowToolbarBtnClass} onClick={onSave} disabled={!isDirty || isSaving}>
          {isSaving ? 'Saving…' : 'Save'}
        </button>
        <button
          type="button"
          onClick={onRun}
          className={runBtnClass}
          style={{ backgroundColor: '#ff6d5a' }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#e85d4d';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#ff6d5a';
          }}
        >
          Execute workflow
        </button>
        {active ? (
          <button type="button" className={flowToolbarBtnClass} onClick={onDeactivate}>
            Deactivate
          </button>
        ) : (
          <button type="button" className={flowToolbarBtnClass} onClick={onActivate} disabled={isDirty}>
            Activate
          </button>
        )}
      </div>
    </div>
  );
};

export default FlowToolbar;
