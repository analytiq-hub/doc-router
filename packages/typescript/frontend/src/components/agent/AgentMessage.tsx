'use client';

import React, { useMemo } from 'react';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AgentChatMessage } from './useAgentChat';
import ToolCallCard from './ToolCallCard';
import ThinkingBlock from './ThinkingBlock';

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

/** URI scheme regex for custom resource links */
const RESOURCE_URI_RE = /^(doc|schema_rev|schema|prompt_rev|prompt|tag|form_rev|form|kb):(.+)$/;

/** Pass through our custom schemes; otherwise use defaultUrlTransform. React-markdown's defaultUrlTransform rejects non-http(s) protocols and returns '', which makes href="" resolve to the current page. */
// eslint-disable-next-line @typescript-eslint/no-unused-vars -- urlTransform signature requires (url, key, node)
function urlTransform(url: string, _key: string, _node: unknown): string {
  if (RESOURCE_URI_RE.test(url)) return url;
  return defaultUrlTransform(url);
}

/** Map a custom URI scheme to an actual route */
function resolveResourceUri(scheme: string, id: string, orgId: string): string {
  switch (scheme) {
    case 'doc':
      return `/orgs/${orgId}/docs/${id}`;
    case 'schema_rev':
      return `/orgs/${orgId}/schemas/${id}`;
    case 'schema':
      return `/orgs/${orgId}/schemas/by-id/${id}`;
    case 'prompt_rev':
      return `/orgs/${orgId}/prompts/${id}`;
    case 'prompt':
      return `/orgs/${orgId}/prompts/by-id/${id}`;
    case 'tag':
      return `/orgs/${orgId}/tags/${id}`;
    case 'form_rev':
      return `/orgs/${orgId}/forms/${id}`;
    case 'form':
      return `/orgs/${orgId}/forms/by-id/${id}`;
    case 'kb':
      return `/orgs/${orgId}/knowledge-bases?tab=edit&kbId=${id}`;
    default:
      return '#';
  }
}

/** Custom markdown components — renders diff code blocks with colored lines and resource links */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function createMarkdownComponents(organizationId: string): Record<string, React.ComponentType<any>> {
  return {
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
    a({ href, children, className, ...props }: { href?: string; children?: React.ReactNode; className?: string }) {
      const linkClass = [className, 'text-blue-600 underline'].filter(Boolean).join(' ');
      const match = href ? RESOURCE_URI_RE.exec(href) : null;
      if (match) {
        const [, scheme, id] = match;
        const url = resolveResourceUri(scheme, id, organizationId);
        return (
          <a href={url} target="_blank" rel="noopener noreferrer" className={linkClass} {...props}>
            {children}
          </a>
        );
      }
      // Regular external links also open in new tab
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" className={linkClass} {...props}>
          {children}
        </a>
      );
    },
  };
}

interface AgentMessageProps {
  message: AgentChatMessage;
  organizationId: string;
  onApprove?: (callId: string) => void;
  onReject?: (callId: string) => void;
  onAlwaysApprove?: (toolName: string) => void;
  pendingCallIds?: Set<string>;
  disabled?: boolean;
  /** Tool calls that are already resolved (e.g. after approve round). */
  resolvedToolCalls?: Map<string, boolean>;
  /** Tool call IDs from loaded threads (executed w/o approval status). */
  executedOnlyIds?: Set<string>;
  /** Read-only tool names (always auto-approved; no approval UI). */
  readOnlyTools?: string[];
}

export default function AgentMessage({
  message,
  organizationId,
  onApprove,
  onReject,
  onAlwaysApprove,
  pendingCallIds,
  disabled,
  resolvedToolCalls,
  executedOnlyIds,
  readOnlyTools,
}: AgentMessageProps) {
  const isUser = message.role === 'user';
  const mdComponents = useMemo(() => createMarkdownComponents(organizationId), [organizationId]);

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
        {!isUser && message.executedRounds?.map((round, idx) => (
          <React.Fragment key={idx}>
            {round.thinking && (
              <ThinkingBlock content={round.thinking} defaultExpanded={true} />
            )}
            {round.tool_calls && round.tool_calls.length > 0 && (
              <div className="mt-1 space-y-0.5">
                {round.tool_calls.map((tc) => (
                  <ToolCallCard
                    key={tc.id}
                    toolCall={{ id: tc.id, name: tc.name, arguments: tc.arguments }}
                    onApprove={() => {}}
                    onReject={() => {}}
                    resolved={true}
                    approved={true}
                    isAutoApproved={readOnlyTools?.includes(tc.name)}
                    showApprovalStatus={false}
                  />
                ))}
              </div>
            )}
          </React.Fragment>
        ))}
        {!isUser && message.thinking && !message.executedRounds?.length && (
          <ThinkingBlock content={message.thinking} defaultExpanded={false} />
        )}
        {message.content && (
          <div className="prose prose-sm max-w-none text-[13px] prose-p:my-1 prose-ul:my-1 prose-pre:my-1 prose-pre:text-xs">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents} urlTransform={urlTransform}>{message.content}</ReactMarkdown>
          </div>
        )}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-1 space-y-0.5">
            {message.toolCalls.map((tc) => {
              const isPending = pendingCallIds?.has(tc.id);
              const resolved = resolvedToolCalls?.has(tc.id);
              const approved = resolved ? resolvedToolCalls?.get(tc.id) : undefined;
              const isAutoApproved = readOnlyTools?.includes(tc.name);
              const showApprovalStatus = !executedOnlyIds?.has(tc.id);
              return (
                <ToolCallCard
                  key={tc.id}
                  toolCall={tc}
                  onApprove={() => onApprove?.(tc.id)}
                  onReject={() => onReject?.(tc.id)}
                  onAlwaysApprove={onAlwaysApprove}
                  disabled={disabled}
                  resolved={resolved ?? !isPending}
                  approved={approved}
                  isAutoApproved={isAutoApproved}
                  showApprovalStatus={showApprovalStatus}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
