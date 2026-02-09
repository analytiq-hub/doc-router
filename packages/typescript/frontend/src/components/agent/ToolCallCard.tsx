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

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50/80 p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-gray-800">{toolCall.name}</span>
        {!resolved && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onApprove}
              disabled={disabled}
              className="p-1.5 rounded text-green-600 hover:bg-green-100 disabled:opacity-50"
              title="Approve"
            >
              <CheckCircleOutlineIcon fontSize="small" />
            </button>
            <button
              type="button"
              onClick={onReject}
              disabled={disabled}
              className="p-1.5 rounded text-red-600 hover:bg-red-100 disabled:opacity-50"
              title="Reject"
            >
              <CancelOutlinedIcon fontSize="small" />
            </button>
          </div>
        )}
        {resolved && (
          <span
            className={
              approved
                ? 'text-green-600 text-xs font-medium'
                : 'text-red-600 text-xs font-medium'
            }
          >
            {approved ? 'Approved' : 'Rejected'}
          </span>
        )}
      </div>
      <div className="mt-2 text-gray-600">
        {Object.keys(argsObj).length > 0 && (
          <>
            <button
              type="button"
              onClick={() => setShowRaw((v) => !v)}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
            >
              {showRaw ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
              {showRaw ? 'Hide' : 'Show'} parameters
            </button>
            {showRaw && (
              <pre className="mt-1 p-2 bg-white rounded border border-gray-200 text-xs overflow-x-auto max-h-40 overflow-y-auto">
                {JSON.stringify(argsObj, null, 2)}
              </pre>
            )}
          </>
        )}
      </div>
    </div>
  );
}
