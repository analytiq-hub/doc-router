'use client';

import React, { useState } from 'react';
import type { PendingToolCall } from './useAgentChat';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

interface ToolCallCardProps {
  toolCall: PendingToolCall;
  onApprove: () => void;
  onReject: () => void;
  disabled?: boolean;
  /** If true, show as already resolved (no buttons). */
  resolved?: boolean;
  approved?: boolean;
}

export default function ToolCallCard({
  toolCall,
  onApprove,
  onReject,
  disabled,
  resolved,
  approved,
}: ToolCallCardProps) {
  const [showRaw, setShowRaw] = useState(false);
  let argsObj: Record<string, unknown> = {};
  try {
    argsObj = JSON.parse(toolCall.arguments || '{}');
  } catch {
    argsObj = {};
  }
  const hasArgs = Object.keys(argsObj).length > 0;

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
          <span className="flex items-center gap-0.5 ml-auto">
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onApprove(); }}
              disabled={disabled}
              className="p-0.5 rounded text-green-600 hover:bg-green-100 disabled:opacity-50"
              title="Approve"
            >
              <CheckCircleOutlineIcon sx={{ fontSize: 14 }} />
            </button>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onReject(); }}
              disabled={disabled}
              className="p-0.5 rounded text-red-600 hover:bg-red-100 disabled:opacity-50"
              title="Reject"
            >
              <CancelOutlinedIcon sx={{ fontSize: 14 }} />
            </button>
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
