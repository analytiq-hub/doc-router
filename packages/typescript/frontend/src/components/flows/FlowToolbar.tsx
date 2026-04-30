'use client';

import React, { useState } from 'react';
import { IconButton, Menu, MenuItem } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import FlowStatusBadge from './FlowStatusBadge';
import {
  FLOW_WORKSPACE_HEADER_HEIGHT_CLASS,
  FLOW_WORKSPACE_TITLE_READ_CLASS,
  flowInlineNameInputClass,
  flowInlineNameMeasureClass,
} from './flowUiClasses';
import { useInlineNameWidthPx } from './useInlineNameWidthPx';

const flowToolbarBtnClass =
  'inline-flex items-center justify-center rounded-md border border-gray-300 bg-white px-2.5 py-1 text-xs font-medium text-gray-800 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50';

const FlowToolbar: React.FC<{
  name: string;
  onNameChange: (name: string) => void;
  active: boolean;
  isDirty: boolean;
  isSaving: boolean;
  onSave: () => void;
  onActivate: () => void;
  onDeactivate: () => void;
  onDownloadFlowJson: () => void;
}> = ({
  name,
  onNameChange,
  active,
  isDirty,
  isSaving,
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
        <FlowStatusBadge active={active} />
        {isDirty && <div className="shrink-0 text-xs text-amber-700">Unsaved changes</div>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <>
          <IconButton size="small" aria-label="More actions" onClick={(e) => setFlowActionsAnchorEl(e.currentTarget)}>
            <MoreVertIcon fontSize="small" />
          </IconButton>
          <Menu
            anchorEl={flowActionsAnchorEl}
            open={Boolean(flowActionsAnchorEl)}
            onClose={() => setFlowActionsAnchorEl(null)}
          >
            <MenuItem
              onClick={() => {
                setFlowActionsAnchorEl(null);
                onDownloadFlowJson();
              }}
            >
              Download
            </MenuItem>
          </Menu>
        </>
        <button type="button" className={flowToolbarBtnClass} onClick={onSave} disabled={!isDirty || isSaving}>
          {isSaving ? 'Saving…' : 'Save'}
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
