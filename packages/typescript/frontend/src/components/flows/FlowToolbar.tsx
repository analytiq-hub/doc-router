'use client';

import React, { useState } from 'react';
import { IconButton, Menu, MenuItem, Tooltip } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import {
  FLOW_WORKSPACE_HEADER_HEIGHT_CLASS,
  FLOW_WORKSPACE_TITLE_READ_CLASS,
  flowInlineNameInputClass,
  flowInlineNameMeasureClass,
} from './flowUiClasses';
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
  const tooltipTitle =
    short != null ? (
      <div style={{ fontSize: 13, lineHeight: 1.35 }}>
        <div style={{ opacity: 0.75, marginBottom: 4 }}>{`Version ${short}`}</div>
        <div>{'Published (active)'}</div>
      </div>
    ) : (
      'Active flow — deactivate from menu'
    );
  return (
    <Tooltip title={tooltipTitle} placement="bottom" enterDelay={400}>
      <span
        className="inline-flex h-[18px] w-[18px] shrink-0 cursor-default items-center justify-center rounded-full bg-emerald-600 shadow-sm"
        role="img"
        aria-label="Flow is active"
      >
        <svg className="h-2.5 w-2.5 text-white" viewBox="0 0 12 12" fill="none" aria-hidden>
          <path d="M2.5 6.2 4.8 8.5 9.5 3.8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    </Tooltip>
  );
};

const FlowToolbar: React.FC<{
  name: string;
  onNameChange: (name: string) => void;
  active: boolean;
  /** `flow.active_flow_revid` when active — used for tooltip (short tail), like n8n version hint. */
  activeFlowRevid?: string | null;
  isDirty: boolean;
  isSaving: boolean;
  activationPending?: boolean;
  onSave: () => void;
  onActivate: () => void;
  onDeactivate: () => void;
  onDownloadFlowJson: () => void;
}> = ({
  name,
  onNameChange,
  active,
  activeFlowRevid = null,
  isDirty,
  isSaving,
  activationPending = false,
  onSave,
  onActivate,
  onDeactivate,
  onDownloadFlowJson,
}) => {
  const [nameHover, setNameHover] = useState(false);
  const [nameFocus, setNameFocus] = useState(false);
  const [flowActionsAnchorEl, setFlowActionsAnchorEl] = useState<null | HTMLElement>(null);
  const showNameField = nameHover || nameFocus;
  const measure = useInlineNameWidthPx(name, 'Flow name');
  const activateDisabled = isDirty || activationPending;
  const deactivateDisabled = activationPending;

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
        {isDirty && <div className="shrink-0 text-xs text-amber-700">Unsaved changes</div>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <button type="button" className={flowToolbarBtnClass} onClick={onSave} disabled={!isDirty || isSaving}>
          {isSaving ? 'Saving…' : 'Save'}
        </button>
        {!active ? (
          <button
            type="button"
            className={flowToolbarBtnClass}
            onClick={onActivate}
            disabled={activateDisabled}
            title={isDirty ? 'Save before activating' : undefined}
          >
            {activationPending ? 'Activating…' : 'Activate'}
          </button>
        ) : (
          <FlowPublishedIndicator revisionIdHint={activeFlowRevid} />
        )}
        <IconButton size="small" aria-label="More actions" edge="end" onClick={(e) => setFlowActionsAnchorEl(e.currentTarget)}>
          <MoreVertIcon fontSize="small" />
        </IconButton>
        <Menu
          anchorEl={flowActionsAnchorEl}
          open={Boolean(flowActionsAnchorEl)}
          onClose={() => setFlowActionsAnchorEl(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          <MenuItem
            onClick={() => {
              setFlowActionsAnchorEl(null);
              onDownloadFlowJson();
            }}
          >
            Download
          </MenuItem>
          {!active ? (
            <MenuItem
              disabled={activateDisabled}
              onClick={() => {
                setFlowActionsAnchorEl(null);
                void onActivate();
              }}
            >
              Activate
            </MenuItem>
          ) : (
            <MenuItem
              disabled={deactivateDisabled}
              onClick={() => {
                setFlowActionsAnchorEl(null);
                void onDeactivate();
              }}
            >
              Deactivate
            </MenuItem>
          )}
        </Menu>
      </div>
    </div>
  );
};

export default FlowToolbar;
