'use client';

import React, { useState } from 'react';
import { Menu, MenuButton, MenuItem, MenuItems } from '@headlessui/react';
import { EllipsisVerticalIcon } from '@heroicons/react/24/outline';
import {
  FLOW_WORKSPACE_HEADER_HEIGHT_CLASS,
  FLOW_WORKSPACE_TITLE_READ_CLASS,
  flowInlineNameInputClass,
  flowInlineNameMeasureClass,
} from './flowUiClasses';
import {
  flowWorkspaceDropdownItemSimpleClass,
  flowWorkspaceMenuPanelClass,
  flowWorkspaceMenuTriggerIconBtnClass,
} from './flowWorkspaceMenu';
import { useInlineNameWidthPx } from './useInlineNameWidthPx';

const flowToolbarBtnClass =
  'inline-flex items-center justify-center rounded-md border border-gray-300 bg-white px-2.5 py-1 text-xs font-medium text-gray-800 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50';

function shortPublishRevisionHint(revid: string | null | undefined): string | undefined {
  if (!revid) return undefined;
  const t = revid.trim();
  if (!t) return undefined;
  return t.length <= 12 ? t : t.slice(-8);
}

const FlowPublishedIndicator: React.FC<{ revisionIdHint?: string | null }> = ({ revisionIdHint }) => {
  const short = shortPublishRevisionHint(revisionIdHint);
  const tip =
    short != null ? `Version ${short} · Published (active)` : 'Active flow — deactivate from ⋮ menu';
  return (
    <span
      className="inline-flex h-[18px] w-[18px] shrink-0 cursor-default items-center justify-center rounded-full bg-emerald-600 shadow-sm"
      role="img"
      aria-label="Flow is active"
      title={tip}
    >
      <svg className="h-2.5 w-2.5 text-white" viewBox="0 0 12 12" fill="none" aria-hidden>
        <path d="M2.5 6.2 4.8 8.5 9.5 3.8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
};

const FlowToolbar: React.FC<{
  name: string;
  onNameChange: (name: string) => void;
  active: boolean;
  /** `flow.active_flow_revid` when active — used for tooltip (short rev id tail). */
  activeFlowRevid?: string | null;
  isDirty: boolean;
  isSaving: boolean;
  activationPending?: boolean;
  /** When set, Save is blocked (tooltip + banner) until the graph is valid. */
  graphSaveBlockedReason?: string | null;
  /** When set, Activate is blocked (e.g. empty canvas). */
  activateBlockedReason?: string | null;
  onSave: () => void;
  onActivate: () => void;
  onDeactivate: () => void;
  onDownloadFlowJson: () => void;
  onOpenSettings: () => void;
  /** When set, shows a Chat test button (flows with Chat Trigger). */
  onOpenChatTest?: () => void;
}> = ({
  name,
  onNameChange,
  active,
  activeFlowRevid = null,
  isDirty,
  isSaving,
  activationPending = false,
  graphSaveBlockedReason = null,
  activateBlockedReason = null,
  onSave,
  onActivate,
  onDeactivate,
  onDownloadFlowJson,
  onOpenSettings,
  onOpenChatTest,
}) => {
  const [nameHover, setNameHover] = useState(false);
  const [nameFocus, setNameFocus] = useState(false);
  const showNameField = nameHover || nameFocus;
  const measure = useInlineNameWidthPx(name, 'Flow name');
  const activateDisabled =
    isDirty || activationPending || Boolean(graphSaveBlockedReason) || Boolean(activateBlockedReason);
  const deactivateDisabled = activationPending;
  const saveDisabled = !isDirty || isSaving || Boolean(graphSaveBlockedReason);

  return (
    <div className={`flex ${FLOW_WORKSPACE_HEADER_HEIGHT_CLASS} shrink-0 items-center justify-between border-b border-gray-200 bg-white px-3`}>
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1 pr-2">
        <div
          className="min-w-0 max-w-[min(100%,42rem)] shrink"
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
            <span className={FLOW_WORKSPACE_TITLE_READ_CLASS} title={name || 'Flow name'}>
              {name.trim() ? name : 'Untitled flow'}
            </span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {onOpenChatTest ? (
          <button type="button" className={flowToolbarBtnClass} onClick={onOpenChatTest}>
            Test chat
          </button>
        ) : null}
        <button
          type="button"
          className={flowToolbarBtnClass}
          onClick={onSave}
          disabled={saveDisabled}
          title={graphSaveBlockedReason ?? undefined}
        >
          {isSaving ? 'Saving…' : 'Save'}
        </button>
        {!active ? (
          <button
            type="button"
            className={flowToolbarBtnClass}
            onClick={onActivate}
            disabled={activateDisabled}
            title={
              activateBlockedReason ??
              (graphSaveBlockedReason ? graphSaveBlockedReason : isDirty ? 'Save before activating' : undefined)
            }
          >
            {activationPending ? 'Activating…' : 'Activate'}
          </button>
        ) : (
          <FlowPublishedIndicator revisionIdHint={activeFlowRevid} />
        )}
        <Menu as="div" className="relative inline-flex">
          <MenuButton className={flowWorkspaceMenuTriggerIconBtnClass} aria-label="More actions">
            <EllipsisVerticalIcon className="h-5 w-5" aria-hidden />
          </MenuButton>
          <MenuItems anchor="bottom end" portal modal={false} className={flowWorkspaceMenuPanelClass}>
            <MenuItem>
              {({ focus }) => (
                <button
                  type="button"
                  className={`${flowWorkspaceDropdownItemSimpleClass} w-full ${focus ? 'bg-gray-100' : ''}`}
                  onClick={() => onOpenSettings()}
                >
                  Settings
                </button>
              )}
            </MenuItem>
            <MenuItem>
              {({ focus }) => (
                <button
                  type="button"
                  className={`${flowWorkspaceDropdownItemSimpleClass} w-full ${focus ? 'bg-gray-100' : ''}`}
                  onClick={() => onDownloadFlowJson()}
                >
                  Download
                </button>
              )}
            </MenuItem>
            {!active ? (
              <MenuItem disabled={activateDisabled}>
                {({ disabled, focus }) => (
                  <button
                    type="button"
                    disabled={disabled}
                    className={`${flowWorkspaceDropdownItemSimpleClass} w-full ${disabled ? 'cursor-not-allowed opacity-45' : ''} ${focus && !disabled ? 'bg-gray-100' : ''}`}
                    onClick={() => void onActivate()}
                  >
                    Activate
                  </button>
                )}
              </MenuItem>
            ) : (
              <MenuItem disabled={deactivateDisabled}>
                {({ disabled, focus }) => (
                  <button
                    type="button"
                    disabled={disabled}
                    className={`${flowWorkspaceDropdownItemSimpleClass} w-full ${disabled ? 'cursor-not-allowed opacity-45' : ''} ${focus && !disabled ? 'bg-gray-100' : ''}`}
                    onClick={() => void onDeactivate()}
                  >
                    Deactivate
                  </button>
                )}
              </MenuItem>
            )}
          </MenuItems>
        </Menu>
      </div>
    </div>
  );
};

export default FlowToolbar;
