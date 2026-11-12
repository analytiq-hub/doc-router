'use client';

import React, { useState } from 'react';
import type { PendingToolCall } from './useAgentChat';
import { CheckCircle2, ChevronDown, CircleX } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

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
  /** If true, tool is always auto-approved (read-only); hide approval UI. */
  isAutoApproved?: boolean;
  /** If false, hide approval status for resolved tools (e.g. loaded threads). */
  showApprovalStatus?: boolean;
}

export default function ToolCallCard({
  toolCall,
  onApprove,
  onReject,
  onAlwaysApprove,
  disabled,
  resolved,
  approved,
  isAutoApproved,
  showApprovalStatus = true,
}: ToolCallCardProps) {
  const [showRaw, setShowRaw] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
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
        onClick={() => setShowRaw((v) => !v)}
      >
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 text-gray-400 transition-transform duration-150 ${showRaw ? 'rotate-180' : ''}`}
          aria-hidden
        />
        <span className="font-medium text-gray-600">{toolCall.name}</span>
        {!resolved && !isAutoApproved && (
          <span className="ml-auto flex items-center overflow-hidden rounded border border-green-200">
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
            <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
              <DropdownMenuTrigger
                disabled={disabled}
                className="border-l border-green-200 px-0.5 py-0.5 text-green-600 hover:bg-green-100 disabled:opacity-50"
                title="More options"
                onClick={(e) => e.stopPropagation()}
              >
                <ChevronDown className="h-4 w-4" aria-hidden />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-[140px]">
                <DropdownMenuItem
                  className="justify-end gap-1 text-[11px] font-medium text-red-700"
                  onClick={(e) => {
                    e.stopPropagation();
                    onReject();
                    setMenuOpen(false);
                  }}
                >
                  Reject
                  <CircleX className="h-4 w-4" aria-hidden />
                </DropdownMenuItem>
                {onAlwaysApprove ? (
                  <DropdownMenuItem
                    className="justify-end gap-1 text-[11px] font-medium text-blue-800"
                    onClick={(e) => {
                      e.stopPropagation();
                      onAlwaysApprove(toolCall.name);
                      onApprove();
                      setMenuOpen(false);
                    }}
                  >
                    Always approve
                    <CheckCircle2 className="h-4 w-4" aria-hidden />
                  </DropdownMenuItem>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
          </span>
        )}
        {resolved && !isAutoApproved && showApprovalStatus && (
          <span
            className={`ml-auto text-[10px] font-medium ${approved ? 'text-green-500' : 'text-red-500'}`}
          >
            {approved ? '✓ approved' : '✗ disapproved'}
          </span>
        )}
      </div>
      {showRaw && (
        <pre className="ml-5 mt-0.5 p-2 bg-gray-50 rounded border border-gray-100 text-[10px] overflow-x-auto max-h-24 overflow-y-auto">
          {hasArgs ? JSON.stringify(argsObj, null, 2) : '{}'}
        </pre>
      )}
    </div>
  );
}
