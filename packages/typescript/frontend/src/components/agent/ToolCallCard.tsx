'use client';

import React, { useState } from 'react';
import type { PendingToolCall } from './useAgentChat';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';

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
    <div className="rounded border border-gray-200 bg-gray-50/80 px-2 py-1 text-xs">
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="font-medium text-gray-700">{toolCall.name}</span>
        {hasArgs && (
          <button
            type="button"
            onClick={() => setShowRaw((v) => !v)}
            className="flex items-center gap-0.5 text-gray-500 hover:text-gray-700"
          >
            {showRaw ? <ExpandLessIcon sx={{ fontSize: 12 }} /> : <ExpandMoreIcon sx={{ fontSize: 12 }} />}
            {showRaw ? 'Hide' : 'Show'} params
          </button>
        )}
        {!resolved && (
          <span className="flex items-center gap-0.5 ml-auto">
            <button
              type="button"
              onClick={onApprove}
              disabled={disabled}
              className="p-0.5 rounded text-green-600 hover:bg-green-100 disabled:opacity-50"
              title="Approve"
            >
              <CheckCircleOutlineIcon sx={{ fontSize: 14 }} />
            </button>
            <button
              type="button"
              onClick={onReject}
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
            className={`ml-auto text-[10px] font-medium ${approved ? 'text-green-600' : 'text-red-600'}`}
          >
            {approved ? '✓' : '✗'}
          </span>
        )}
      </div>
      {showRaw && hasArgs && (
        <pre className="mt-1 p-1.5 bg-white rounded border border-gray-200 text-[10px] overflow-x-auto max-h-24 overflow-y-auto">
          {JSON.stringify(argsObj, null, 2)}
        </pre>
      )}
    </div>
  );
}
