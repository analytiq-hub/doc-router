'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AgentChatMessage } from './useAgentChat';
import ToolCallCard from './ToolCallCard';

/** Renders diff content with colored add/remove lines, Cursor-style */
function DiffBlock({ content }: { content: string }) {
  const lines = content.split('\n');
  return (
    <div className="rounded-md border border-gray-200 overflow-hidden my-2">
      {lines.map((line, i) => {
        const isAdd = line.startsWith('+') && !line.startsWith('+++');
        const isRemove = line.startsWith('-') && !line.startsWith('---');
        const isMeta =
          line.startsWith('@@') ||
          line.startsWith('diff ') ||
          line.startsWith('---') ||
          line.startsWith('+++') ||
          line.startsWith('index ');
        return (
          <div
            key={i}
            className={`px-3 font-mono text-[12px] leading-5 whitespace-pre-wrap ${
              isAdd
                ? 'bg-green-100/70 text-green-900'
                : isRemove
                  ? 'bg-red-100/70 text-red-900'
                  : isMeta
                    ? 'bg-blue-50/60 text-blue-700 text-[11px]'
                    : 'text-gray-700'
            }`}
          >
            {line || '\u00A0'}
          </div>
        );
      })}
    </div>
  );
}

/** Custom markdown components — renders diff code blocks with colored lines */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const markdownComponents: Record<string, React.ComponentType<any>> = {
  pre({ children, ...props }: { children: React.ReactNode }) {
    const child = React.Children.toArray(children)[0];
    if (React.isValidElement(child)) {
      const childProps = child.props as Record<string, unknown>;
      const className = String(childProps?.className || '');
      if (className.includes('language-diff')) {
        const content = String(childProps?.children || '').replace(/\n$/, '');
        return <DiffBlock content={content} />;
      }
    }
    return <pre {...props}>{children}</pre>;
  },
};

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
      className="w-full"
      data-testid={isUser ? 'agent-message-user' : 'agent-message-assistant'}
    >
      <div
        className={
          isUser
            ? 'w-full rounded-lg px-3 py-2 bg-gray-50 text-gray-900 border border-gray-200'
            : 'w-full text-gray-900'
        }
      >
        {message.content && (
          <div className="prose prose-sm max-w-none text-[13px] prose-p:my-1 prose-ul:my-1 prose-pre:my-1 prose-pre:text-xs">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{message.content}</ReactMarkdown>
          </div>
        )}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-1 space-y-0.5">
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
