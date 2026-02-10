'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AgentChatMessage, PendingToolCall } from './useAgentChat';
import ToolCallCard from './ToolCallCard';

interface AgentMessageProps {
  message: AgentChatMessage;
  onApprove?: (callId: string) => void;
  onReject?: (callId: string) => void;
  pendingCallIds?: Set<string>;
  disabled?: boolean;
  /** Tool calls that are already resolved (e.g. after approve round). */
  resolvedToolCalls?: Map<string, boolean>;
}

export default function AgentMessage({
  message,
  onApprove,
  onReject,
  pendingCallIds,
  disabled,
  resolvedToolCalls,
}: AgentMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div
      className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}
      data-testid={isUser ? 'agent-message-user' : 'agent-message-assistant'}
    >
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 ${
          isUser
            ? 'bg-blue-100 text-blue-900'
            : 'bg-gray-100 text-gray-900 border border-gray-200'
        }`}
      >
        {message.content && (
          <div className="prose prose-sm max-w-none text-[13px] prose-p:my-1 prose-ul:my-1 prose-pre:my-1 prose-pre:text-xs">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        )}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-1.5 space-y-1">
            {message.toolCalls.map((tc) => {
              const isPending = pendingCallIds?.has(tc.id);
              const resolved = resolvedToolCalls?.has(tc.id);
              const approved = resolved ? resolvedToolCalls?.get(tc.id) : undefined;
              return (
                <ToolCallCard
                  key={tc.id}
                  toolCall={tc}
                  onApprove={() => onApprove?.(tc.id)}
                  onReject={() => onReject?.(tc.id)}
                  disabled={disabled}
                  resolved={resolved ?? !isPending}
                  approved={approved}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
