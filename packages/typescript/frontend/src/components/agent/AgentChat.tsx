'use client';

import React, { useEffect, useRef } from 'react';
import type { AgentChatMessage, PendingToolCall } from './useAgentChat';
import AgentMessage from './AgentMessage';

interface AgentChatProps {
  messages: AgentChatMessage[];
  pendingToolCalls: PendingToolCall[];
  loading: boolean;
  error: string | null;
  onApprove: (approvals: Array<{ call_id: string; approved: boolean }>) => void;
  disabled?: boolean;
}

/** Tracks which tool call IDs we've already resolved (approved/rejected) in a previous round. */
const resolvedFromMessages = (messages: AgentChatMessage[]): Map<string, boolean> => {
  const map = new Map<string, boolean>();
  messages.forEach((m) => {
    if (m.role === 'assistant' && m.toolCalls?.length) {
      m.toolCalls.forEach((tc) => {
        if ((tc as PendingToolCall & { approved?: boolean }).approved !== undefined) {
          map.set(tc.id, (tc as PendingToolCall & { approved?: boolean }).approved ?? false);
        }
      });
    }
  });
  return map;
};

const pendingCallIds = (pending: PendingToolCall[]) => new Set(pending.map((tc) => tc.id));

export default function AgentChat({
  messages,
  pendingToolCalls,
  loading,
  error,
  onApprove,
  disabled,
}: AgentChatProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const resolvedMap = resolvedFromMessages(messages);
  const pendingIds = pendingCallIds(pendingToolCalls);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleApproveOne = (callId: string, approved: boolean) => {
    onApprove(
      pendingToolCalls.map((tc) => ({
        call_id: tc.id,
        approved: tc.id === callId ? approved : !approved,
      }))
    );
  };

  const handleApproveAll = () => {
    onApprove(pendingToolCalls.map((tc) => ({ call_id: tc.id, approved: true })));
  };

  const handleRejectAll = () => {
    onApprove(pendingToolCalls.map((tc) => ({ call_id: tc.id, approved: false })));
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && !loading && (
          <div className="text-gray-500 text-xs text-center py-8">
            Send a message to start. Ask the agent to create a schema, create a prompt, or run extraction on this document.
          </div>
        )}
        {messages.map((msg, idx) => (
          <AgentMessage
            key={idx}
            message={msg}
            onApprove={(id) => handleApproveOne(id, true)}
            onReject={(id) => handleApproveOne(id, false)}
            pendingCallIds={pendingIds}
            disabled={disabled}
            resolvedToolCalls={resolvedMap}
          />
        ))}
        {pendingToolCalls.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-500">Pending actions:</span>
            <button
              type="button"
              onClick={handleApproveAll}
              disabled={disabled}
              className="px-2 py-1 text-xs rounded bg-green-100 text-green-700 hover:bg-green-200 disabled:opacity-50"
            >
              Approve all
            </button>
            <button
              type="button"
              onClick={handleRejectAll}
              disabled={disabled}
              className="px-2 py-1 text-xs rounded bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-50"
            >
              Reject all
            </button>
          </div>
        )}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-lg px-3 py-2 bg-gray-100 border border-gray-200 text-gray-500 text-xs">
              Thinking…
            </div>
          </div>
        )}
        {error && (
          <div className="rounded-lg px-3 py-2 bg-red-50 border border-red-200 text-red-700 text-xs">
            {error}
          </div>
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}
