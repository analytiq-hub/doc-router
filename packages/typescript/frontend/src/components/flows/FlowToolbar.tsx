import React from 'react';
import { UserIcon } from '@heroicons/react/24/outline';
import FlowStatusBadge from './FlowStatusBadge';
import { flowNameBreadcrumbInputClass } from './flowUiClasses';

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
  /** Breadcrumb left segment (e.g. org or collection name). */
  contextLabel?: string;
}> = ({
  name,
  onNameChange,
  active,
  isDirty,
  isSaving,
  onSave,
  onRun,
  onActivate,
  onDeactivate,
  contextLabel = 'Flows',
}) => {
  return (
    <div className="flex items-center justify-between border-b border-gray-200 bg-white px-3 py-2">
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1 pr-2">
        <UserIcon className="h-4 w-4 shrink-0 text-gray-500" aria-hidden />
        <span className="shrink-0 text-sm text-gray-500">{contextLabel}</span>
        <span className="shrink-0 text-sm text-gray-300">/</span>
        <input
          className={flowNameBreadcrumbInputClass}
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="Flow name"
          aria-label="Flow name"
        />
        <button type="button" className="shrink-0 text-sm text-gray-500 opacity-50" tabIndex={-1} disabled title="Not available yet">
          + Add tag
        </button>
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
