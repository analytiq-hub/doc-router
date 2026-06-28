'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FlowChatStreamEvent, FlowNode, RevisionSnapshotPayload } from '@docrouter/sdk';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { XMarkIcon } from '@heroicons/react/24/outline';
import SendIcon from '@mui/icons-material/Send';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const PANEL_WIDTH_PX = 400;

type ChatRole = 'user' | 'assistant' | 'system';

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  toolCalls?: Array<{
    tool: string;
    arguments?: Record<string, unknown>;
    preview?: string;
    success?: boolean;
  }>;
};

function splitInitialMessages(raw: string | undefined): string[] {
  if (!raw?.trim()) return [];
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

function newMessageId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

const FlowEditorChatPanel: React.FC<{
  organizationId: string;
  flowId: string;
  flowRevid?: string | null;
  chatTriggerNode: FlowNode;
  buildRevisionSnapshot: () => RevisionSnapshotPayload | null;
  onClose: () => void;
  onExecutionId?: (executionId: string) => void;
  /** When false, hide streamed tool-call details in the chat transcript. */
  showToolTrace?: boolean;
}> = ({
  organizationId,
  flowId,
  flowRevid,
  chatTriggerNode,
  buildRevisionSnapshot,
  onClose,
  onExecutionId,
  showToolTrace = true,
}) => {
  const api = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const params = chatTriggerNode.parameters ?? {};
  const responseMode = String(params.response_mode ?? 'streaming');
  const isStreamingMode = responseMode === 'streaming';
  const placeholder = String(params.input_placeholder ?? 'Type your message…');
  const title = String(params.title ?? '').trim() || 'Chat test';
  const subtitle = String(params.subtitle ?? '').trim();

  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    splitInitialMessages(String(params.initial_messages ?? '')).map((line) => ({
      id: newMessageId(),
      role: 'system' as const,
      content: line,
    })),
  );
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pendingToolsRef = useRef<NonNullable<ChatMessage['toolCalls']>>([]);
  const streamFinishedRef = useRef(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy]);

  const finishStreamingTurn = useCallback(() => {
    if (streamFinishedRef.current) return;
    streamFinishedRef.current = true;
    setBusy(false);
    abortRef.current = null;
  }, []);

  const appendAssistantDelta = useCallback((chunk: string) => {
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last?.role === 'assistant') {
        return [...prev.slice(0, -1), { ...last, content: last.content + chunk }];
      }
      return [...prev, { id: newMessageId(), role: 'assistant', content: chunk }];
    });
  }, []);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;

    const revision_snapshot = buildRevisionSnapshot();
    if (!revision_snapshot) {
      setError('Flow is still loading — wait a moment and try again.');
      return;
    }

    abortRef.current?.abort();
    streamFinishedRef.current = false;
    pendingToolsRef.current = [];

    setError(null);
    setInput('');
    setBusy(true);
    setMessages((prev) => [...prev, { id: newMessageId(), role: 'user', content: text }]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      if (isStreamingMode) {
        setMessages((prev) => [...prev, { id: newMessageId(), role: 'assistant', content: '' }]);

        await api.runFlowChatTest(
          flowId,
          {
            chatInput: text,
            sessionId,
            flow_revid: flowRevid ?? null,
            revision_snapshot,
          },
          (event: FlowChatStreamEvent) => {
            if (event.type === 'meta') {
              if (event.session_id) setSessionId(event.session_id);
              if (event.execution_id) onExecutionId?.(event.execution_id);
              return;
            }
            if (event.type === 'content' && event.chunk) {
              appendAssistantDelta(event.chunk);
              return;
            }
            if (event.type === 'tool_call') {
              if (!showToolTrace) return;
              pendingToolsRef.current.push({
                tool: event.tool,
                arguments: event.arguments,
              });
              return;
            }
            if (event.type === 'tool_result') {
              if (!showToolTrace) return;
              const match = [...pendingToolsRef.current]
                .reverse()
                .find((t) => t.tool === event.tool && !t.preview);
              if (match) {
                match.preview = event.preview;
                match.success = event.success;
              }
              return;
            }
            if (event.type === 'end') {
              if (event.session_id) setSessionId(event.session_id);
              if (event.execution_id) onExecutionId?.(event.execution_id);
              const toolCalls =
                showToolTrace && pendingToolsRef.current.length > 0
                  ? [...pendingToolsRef.current]
                  : undefined;
              setMessages((prev) => {
                const out = [...prev];
                const last = out[out.length - 1];
                if (last?.role === 'assistant') {
                  out[out.length - 1] = {
                    ...last,
                    content: last.content || event.text || '',
                    toolCalls: toolCalls ?? last.toolCalls,
                  };
                }
                return out;
              });
              finishStreamingTurn();
              return;
            }
            if (event.type === 'error') {
              setError(event.message || 'Chat run failed');
              finishStreamingTurn();
            }
          },
          (err) => {
            if (controller.signal.aborted) return;
            setError(getApiErrorMsg(err) || 'Chat stream failed');
            finishStreamingTurn();
          },
          controller.signal,
        );
        finishStreamingTurn();
      } else {
        const res = await api.runFlowChatTest(flowId, {
          chatInput: text,
          sessionId,
          flow_revid: flowRevid ?? null,
          revision_snapshot,
        });
        if (res && typeof res === 'object' && 'text' in res) {
          const buffered = res as { text: string; session_id?: string; execution_id?: string };
          if (buffered.session_id) setSessionId(buffered.session_id);
          if (buffered.execution_id) onExecutionId?.(buffered.execution_id);
          setMessages((prev) => [
            ...prev,
            { id: newMessageId(), role: 'assistant', content: buffered.text || '' },
          ]);
        }
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      setError(getApiErrorMsg(err) || 'Failed to send message');
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === 'assistant' && !last.content.trim()) {
          return prev.slice(0, -1);
        }
        return prev;
      });
    } finally {
      if (!streamFinishedRef.current) {
        setBusy(false);
        abortRef.current = null;
      }
    }
  }, [
    api,
    appendAssistantDelta,
    buildRevisionSnapshot,
    busy,
    finishStreamingTurn,
    flowId,
    flowRevid,
    input,
    isStreamingMode,
    onExecutionId,
    sessionId,
    showToolTrace,
  ]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <>
      <div className="fixed inset-0 z-[150] bg-black/20" onClick={onClose} aria-hidden />
      <aside
        className="fixed right-0 top-0 z-[160] flex h-full min-w-0 flex-col border-l border-[#dfe3e9] bg-white shadow-xl"
        style={{ width: `min(100vw, ${PANEL_WIDTH_PX}px)` }}
        role="dialog"
        aria-modal
        aria-labelledby="flow-editor-chat-title"
      >
        <header className="shrink-0 border-b border-[#dfe3e9] bg-[#f3f6f9] px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 id="flow-editor-chat-title" className="text-base font-bold text-[#22262b]">
                {title}
              </h2>
              {subtitle ? <p className="mt-0.5 text-sm text-[#5d656e]">{subtitle}</p> : null}
              <p className="mt-1 text-xs text-[#9ca3af]">
                Editor test · {isStreamingMode ? 'streaming' : 'buffered'}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close chat"
              className="-mr-1 shrink-0 rounded-md p-1.5 text-[#5d656e] hover:bg-white/70"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          {messages.length === 0 ? (
            <p className="text-sm text-gray-500">Send a message to test the Chat Trigger flow.</p>
          ) : (
            <div className="space-y-3">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={
                    msg.role === 'user'
                      ? 'ml-6 rounded-lg bg-blue-50 px-3 py-2 text-sm text-[#1e3a5f]'
                      : msg.role === 'system'
                        ? 'rounded-lg border border-dashed border-[#dfe3e9] bg-[#fafbfc] px-3 py-2 text-sm text-[#5d656e]'
                        : 'mr-2 rounded-lg bg-[#f3f6f9] px-3 py-2 text-sm text-[#22262b]'
                  }
                >
                  {msg.role === 'assistant' ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]} className="prose prose-sm max-w-none">
                      {msg.content || (busy ? '…' : '')}
                    </ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                  {showToolTrace && msg.toolCalls && msg.toolCalls.length > 0 ? (
                    <ul className="mt-2 space-y-1 border-t border-[#e5e7eb] pt-2 text-xs text-[#5d656e]">
                      {msg.toolCalls.map((tc, i) => (
                        <li key={`${tc.tool}-${i}`}>
                          <span className="font-medium">{tc.tool}</span>
                          {tc.preview ? `: ${tc.preview}` : ''}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {error ? <div className="shrink-0 px-4 pb-2 text-sm text-red-600">{error}</div> : null}

        <div className="shrink-0 border-t border-[#dfe3e9] p-3">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={busy}
              rows={2}
              className="min-h-[2.5rem] flex-1 resize-none rounded-lg border border-[#dfe3e9] px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
            />
            <button
              type="button"
              onClick={() => void handleSend()}
              disabled={busy || !input.trim()}
              className="flex shrink-0 items-center justify-center rounded-lg bg-blue-600 px-3 py-2 text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
              aria-label="Send message"
            >
              <SendIcon sx={{ fontSize: '1.25rem' }} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
};

export default FlowEditorChatPanel;
