'use client';

import React, { useState } from 'react';
import type { PendingToolCall } from './useAgentChat';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { Menu, MenuItem } from '@mui/material';

interface ToolCallCardProps {
  toolCall: PendingToolCall;
  onApprove: () => void;
  onReject: () => void;
  /** When provided, shows "Always approve" option that adds this tool to auto-approved and approves this call. */
  onAlwaysApprove?: (toolName: string) => void;
  disabled?: boolean;
  /** If true, show as already resolved (no buttons). */
  resolved?: boolean;
  approved?: boolean;
}

export default function ToolCallCard({
  toolCall,
  onApprove,
  onReject,
  onAlwaysApprove,
  disabled,
  resolved,
  approved,
}: ToolCallCardProps) {
  const [showRaw, setShowRaw] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  let argsObj: Record<string, unknown> = {};
  try {
    argsObj = JSON.parse(toolCall.arguments || '{}');
  } catch {
    argsObj = {};
  }
  const hasArgs = Object.keys(argsObj).length > 0;

  const handleMenuClose = () => setMenuAnchor(null);

  return (
    <div className="group">
      <div
        className="flex items-center gap-1.5 py-0.5 text-xs cursor-pointer select-none"
        onClick={() => hasArgs && setShowRaw((v) => !v)}
      >
        {hasArgs ? (
          <ExpandMoreIcon
            sx={{ fontSize: 14 }}
            className={`text-gray-400 transition-transform duration-150 ${showRaw ? 'rotate-180' : ''}`}
          />
        ) : (
          <span className="w-3.5" />
        )}
        <span className="font-medium text-gray-600">{toolCall.name}</span>
        {!resolved && (
          <span className="flex items-center ml-auto rounded overflow-hidden border border-green-200">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onApprove();
              }}
              disabled={disabled}
              className="px-2 py-0.5 text-[11px] font-medium text-green-700 bg-green-50 hover:bg-green-100 disabled:opacity-50"
              title="Approve"
            >
              Approve
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setMenuAnchor(e.currentTarget);
              }}
              disabled={disabled}
              className="px-0.5 py-0.5 text-green-600 hover:bg-green-100 border-l border-green-200 disabled:opacity-50"
              title="More options"
            >
              <ArrowDropDownIcon sx={{ fontSize: 16 }} />
            </button>
            <Menu
              anchorEl={menuAnchor}
              open={Boolean(menuAnchor)}
              onClose={handleMenuClose}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
              slotProps={{
                paper: {
                  sx: { width: 140, minWidth: 140 },
                },
              }}
            >
              <MenuItem
                onClick={() => {
                  onReject();
                  handleMenuClose();
                }}
                sx={{
                  display: 'flex',
                  width: '100%',
                  justifyContent: 'flex-end',
                  alignItems: 'center',
                  gap: 0.5,
                  py: 0.5,
                  px: 1.5,
                  fontSize: '11px',
                  fontWeight: 500,
                  color: '#b91c1c',
                }}
              >
                Reject
                <CancelOutlinedIcon sx={{ fontSize: 16 }} />
              </MenuItem>
              {onAlwaysApprove && (
                <MenuItem
                  onClick={() => {
                    onAlwaysApprove(toolCall.name);
                    onApprove();
                    handleMenuClose();
                  }}
                  sx={{
                    display: 'flex',
                    width: '100%',
                    justifyContent: 'flex-end',
                    alignItems: 'center',
                    gap: 0.5,
                    py: 0.5,
                    px: 1.5,
                    fontSize: '11px',
                    fontWeight: 500,
                    color: '#1d4ed8',
                  }}
                >
                  Always approve
                  <CheckCircleOutlineIcon sx={{ fontSize: 16 }} />
                </MenuItem>
              )}
            </Menu>
          </span>
        )}
        {resolved && (
          <span
            className={`ml-auto text-[10px] font-medium ${approved ? 'text-green-500' : 'text-red-500'}`}
          >
            {approved ? '✓ approved' : '✗ rejected'}
          </span>
        )}
      </div>
      {showRaw && hasArgs && (
        <pre className="ml-5 mt-0.5 p-2 bg-gray-50 rounded border border-gray-100 text-[10px] overflow-x-auto max-h-24 overflow-y-auto">
          {JSON.stringify(argsObj, null, 2)}
        </pre>
      )}
    </div>
  );
}
