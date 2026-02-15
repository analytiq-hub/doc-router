'use client';

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import ReplayIcon from '@mui/icons-material/Replay';
import type { AgentChatMessage, PendingToolCall } from './useAgentChat';
import AgentMessage from './AgentMessage';
import ThinkingBlock from './ThinkingBlock';

/** One user message plus all following assistant messages until the next user message. */
interface ChatTurn {
  user: AgentChatMessage;
  assistants: AgentChatMessage[];
}

function messagesToTurns(messages: AgentChatMessage[]): ChatTurn[] {
  const turns: ChatTurn[] = [];
  let current: ChatTurn | null = null;
  for (const m of messages) {
    if (m.role === 'user') {
      current = { user: m, assistants: [] };
      turns.push(current);
    } else if (current) {
      current.assistants.push(m);
    }
  }
  return turns;
}

interface AgentChatProps {
  organizationId: string;
  messages: AgentChatMessage[];
  pendingToolCalls: PendingToolCall[];
  /** Call IDs approved/rejected this session; merged with message-based resolution. */
  approvedCallIds?: Map<string, boolean>;
  /** Read-only tool names (always auto-approved; no approval UI). */
  readOnlyTools?: string[];
  loading: boolean;
  error: string | null;
  onApprove: (approvals: Array<{ call_id: string; approved: boolean }>) => void;
  /** When user selects "Always approve" on a tool, add it to auto-approved list. */
  onAlwaysApprove?: (toolName: string) => void;
  /** When user edits and resubmits the sticky question, restart conversation from that turn. */
  onEditAndResubmit?: (newContent: string, turnIndex: number) => void;
  disabled?: boolean;
}

/** Collect tool call IDs from executed rounds. */
function toolCallIdsFromExecutedRounds(rounds?: Array<{ tool_calls?: Array<{ id: string }> }>): Set<string> {
  const ids = new Set<string>();
  rounds?.forEach((r) => r.tool_calls?.forEach((tc) => ids.add(tc.id)));
  return ids;
}

/** Tool calls from loaded threads - hide approval status for all (no Approve button on refresh). */
function executedOnlyIdsFromMessages(
  messages: AgentChatMessage[],
  hasPendingApproval: boolean
): Set<string> {
  const ids = new Set<string>();
  if (hasPendingApproval) {
    return ids;
  }
  messages.forEach((m, i) => {
    const executedIdsInNext = (() => {
      const nextMsg = messages[i + 1];
      return nextMsg?.role === 'assistant' && nextMsg.executedRounds?.length
        ? toolCallIdsFromExecutedRounds(nextMsg.executedRounds)
        : null;
    })();
    const executedIdsInSame = m.executedRounds?.length
      ? toolCallIdsFromExecutedRounds(m.executedRounds)
      : null;
    if (m.role === 'assistant') {
      m.toolCalls?.forEach((tc) => {
        if ((tc as PendingToolCall & { approved?: boolean }).approved === undefined &&
            (executedIdsInNext?.has(tc.id) || executedIdsInSame?.has(tc.id))) {
          ids.add(tc.id);
        }
      });
      executedIdsInSame?.forEach((id) => ids.add(id));
      executedIdsInNext?.forEach((id) => ids.add(id));
    }
  });
  return ids;
}

/** Tool call IDs from history - when no pending approval, hide approval UI for all. */
function allToolCallIdsFromMessages(messages: AgentChatMessage[]): Set<string> {
  const ids = new Set<string>();
  messages.forEach((m) => {
    if (m.role === 'assistant') {
      m.toolCalls?.forEach((tc) => ids.add(tc.id));
      m.executedRounds?.forEach((r) => r.tool_calls?.forEach((tc) => ids.add(tc.id)));
    }
  });
  return ids;
}

/** Tracks which tool call IDs we've already resolved (approved/rejected) in a previous round. */
const resolvedFromMessages = (
  messages: AgentChatMessage[],
  approvedCallIds?: Map<string, boolean>
): Map<string, boolean> => {
  const map = new Map<string, boolean>();
  messages.forEach((m, i) => {
    const executedIdsInNext = (() => {
      const nextMsg = messages[i + 1];
      return nextMsg?.role === 'assistant' && nextMsg.executedRounds?.length
        ? toolCallIdsFromExecutedRounds(nextMsg.executedRounds)
        : null;
    })();
    const executedIdsInSame = m.executedRounds?.length
      ? toolCallIdsFromExecutedRounds(m.executedRounds)
      : null;
    if (m.role === 'assistant' && m.toolCalls?.length) {
      m.toolCalls.forEach((tc) => {
        if ((tc as PendingToolCall & { approved?: boolean }).approved !== undefined) {
          map.set(tc.id, (tc as PendingToolCall & { approved?: boolean }).approved ?? false);
        } else if (executedIdsInNext?.has(tc.id) || executedIdsInSame?.has(tc.id)) {
          map.set(tc.id, true);
        }
      });
    }
  });
  approvedCallIds?.forEach((v, k) => map.set(k, v));
  return map;
};

const pendingCallIds = (pending: PendingToolCall[]) => new Set(pending.map((tc) => tc.id));

const STICKY_HEADER_HEIGHT = 44;

/** Lines in text (at least 1). Used to size collapsed question to content, max 3 lines. */
function lineCount(text: string): number {
  if (!text.trim()) return 1;
  const n = (text.match(/\n/g) || []).length + 1;
  return Math.max(1, n);
}

function collapsedRows(text: string): number {
  return Math.min(3, lineCount(text));
}

/** Min height in rem so N lines + padding are fully visible (avoids chopped text). Uses generous line height and extra for 2+ lines to account for wrapping in narrower panel. */
function collapsedMinHeightRem(lines: number): number {
  const paddingRem = 1;
  const lineHeightRem = 1.5;
  const extraForWrapping = lines >= 2 ? 0.5 : 0;
  return paddingRem + lines * lineHeightRem + extraForWrapping;
}

export default function AgentChat({
  organizationId,
  messages,
  pendingToolCalls,
  approvedCallIds,
  readOnlyTools,
  loading,
  error,
  onApprove,
  onAlwaysApprove,
  onEditAndResubmit,
  disabled,
}: AgentChatProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const turnRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [stickyQuestion, setStickyQuestion] = useState<string | null>(null);
  const [stickyTurnIndex, setStickyTurnIndex] = useState(0);
  const [editingSticky, setEditingSticky] = useState(false);
  const [stickyInputValue, setStickyInputValue] = useState('');
  const [editingPanelTurnIndex, setEditingPanelTurnIndex] = useState<number | null>(null);
  const [editingPanelValue, setEditingPanelValue] = useState('');

  const resolvedMap = resolvedFromMessages(messages, approvedCallIds);
  const hasPendingApproval = pendingToolCalls.length > 0;
  const executedOnlyIds = useMemo(
    () =>
      approvedCallIds?.size
        ? new Set<string>()
        : hasPendingApproval
          ? executedOnlyIdsFromMessages(messages, true)
          : allToolCallIdsFromMessages(messages),
    [messages, approvedCallIds?.size, hasPendingApproval]
  );
  const pendingIds = pendingCallIds(pendingToolCalls);
  // For multi-call batches, hide individual approve/reject buttons — use batch buttons instead.
  const individualPendingIds = pendingToolCalls.length > 1 ? new Set<string>() : pendingIds;
  const turns = useMemo(() => messagesToTurns(messages), [messages]);

  // Track last computed values to avoid setState when unchanged (prevents ResizeObserver
  // feedback loop: setState -> re-render -> layout change -> ResizeObserver -> setState).
  const lastStickyRef = useRef<{ text: string | null; index: number } | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const updateStickyQuestion = useCallback(() => {
    const container = scrollRef.current;
    if (!container || turns.length === 0) {
      if (lastStickyRef.current?.text !== null || lastStickyRef.current?.index !== 0) {
        lastStickyRef.current = { text: null, index: 0 };
        setStickyQuestion(null);
        setStickyTurnIndex(0);
      }
      return;
    }
    // Use getBoundingClientRect for reliable comparison regardless of nesting
    const containerTop = container.getBoundingClientRect().top;
    const threshold = containerTop + STICKY_HEADER_HEIGHT + 8;
    let currentIndex = 0;
    for (let i = 0; i < turnRefs.current.length; i++) {
      const el = turnRefs.current[i];
      if (el && el.getBoundingClientRect().top <= threshold) {
        currentIndex = i;
      }
    }
    const turn = turns[currentIndex];
    const text = turn?.user.content?.trim() ?? null;
    if (
      lastStickyRef.current?.text === text &&
      lastStickyRef.current?.index === currentIndex
    ) {
      return;
    }
    lastStickyRef.current = { text, index: currentIndex };
    setStickyQuestion(text);
    setStickyTurnIndex(currentIndex);
  }, [turns]);

  useEffect(() => {
    setEditingSticky(false);
  }, [stickyTurnIndex]);

  useEffect(() => {
    turnRefs.current = turnRefs.current.slice(0, turns.length);
  }, [turns.length]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    updateStickyQuestion();
    container.addEventListener('scroll', updateStickyQuestion, { passive: true });
    const ro = new ResizeObserver(updateStickyQuestion);
    ro.observe(container);
    return () => {
      container.removeEventListener('scroll', updateStickyQuestion);
      ro.disconnect();
    };
  }, [updateStickyQuestion]);

  const handleApproveOne = (callId: string, approved: boolean) => {
    // Only used for single-call batches; multi-call batches use Approve/Reject all.
    onApprove([{ call_id: callId, approved }]);
  };

  const handleApproveAll = () => {
    onApprove(pendingToolCalls.map((tc) => ({ call_id: tc.id, approved: true })));
  };

  const handleRejectAll = () => {
    onApprove(pendingToolCalls.map((tc) => ({ call_id: tc.id, approved: false })));
  };

  const handleStickyFocus = () => {
    setEditingSticky(true);
    setStickyInputValue(stickyQuestion ?? '');
  };

  const stickyDisplayValue = editingSticky ? stickyInputValue : (stickyQuestion ?? '');

  const handleStickySubmit = () => {
    const text = stickyDisplayValue.trim();
    if (text && onEditAndResubmit && !disabled) {
      onEditAndResubmit(text, stickyTurnIndex);
      setEditingSticky(false);
    }
  };

  const handlePanelQuestionFocus = (turnIdx: number) => {
    setEditingPanelTurnIndex(turnIdx);
    setEditingPanelValue(turns[turnIdx]?.user.content ?? '');
  };

  const handlePanelQuestionResubmit = (turnIdx: number) => {
    const text = (editingPanelTurnIndex === turnIdx ? editingPanelValue : turns[turnIdx]?.user.content ?? '').trim();
    if (text && onEditAndResubmit && !disabled) {
      onEditAndResubmit(text, turnIdx);
      setEditingPanelTurnIndex(null);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div ref={scrollRef} className="flex-1 overflow-y-auto min-h-0">
        <div className="w-full min-w-0 px-3">
          {turns.length > 0 && (
            <div
              className="sticky top-0 z-10 shrink-0 flex items-start gap-2 py-2 bg-white border-b border-gray-200"
              style={{ minHeight: STICKY_HEADER_HEIGHT }}
            >
              <textarea
              value={stickyDisplayValue}
              onChange={(e) => editingSticky && setStickyInputValue(e.target.value)}
              onFocus={handleStickyFocus}
              onBlur={() => { if (!stickyInputValue.trim()) setEditingSticky(false); }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleStickySubmit();
                }
              }}
              placeholder="Question for this turn"
              rows={editingSticky ? 10 : collapsedRows(stickyDisplayValue)}
              style={!editingSticky ? { minHeight: `${collapsedMinHeightRem(collapsedRows(stickyDisplayValue))}rem` } : undefined}
              className={`flex-1 min-w-0 text-sm text-gray-700 bg-transparent border-0 py-1 px-0 focus:outline-none focus:ring-0 placeholder:text-gray-400 ${
                editingSticky
                  ? 'max-h-[15rem] overflow-y-auto resize-none'
                  : 'max-h-[10rem] overflow-hidden resize-none'
              }`}
              disabled={disabled}
              title="Click to expand. Edit and press Enter to resubmit (Shift+Enter for newline)"
            />
            {onEditAndResubmit && (
              <button
                type="button"
                onClick={handleStickySubmit}
                disabled={disabled || !stickyDisplayValue.trim()}
                className="shrink-0 p-1.5 rounded text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-50"
                title="Resubmit from this point"
              >
                <ReplayIcon sx={{ fontSize: 16 }} />
              </button>
            )}
            </div>
          )}
          <div className="pt-3 pb-3 space-y-3">
          {messages.length === 0 && !loading && (
            <div className="text-gray-500 text-xs text-center py-8">
              Send a message to start. Ask the agent to create a schema, create a prompt, or run extraction on this document.
            </div>
          )}
          {turns.map((turn, turnIdx) => (
            <div
              key={turnIdx}
              ref={(el) => { turnRefs.current[turnIdx] = el; }}
              className="space-y-3"
            >
              <div className={`w-full rounded-lg border border-gray-200 bg-gray-50 min-w-0 flex items-start gap-2${turnIdx === stickyTurnIndex ? ' hidden' : ''}`}>
                <textarea
                  value={editingPanelTurnIndex === turnIdx ? editingPanelValue : (turn.user.content ?? '')}
                  onChange={(e) => editingPanelTurnIndex === turnIdx && setEditingPanelValue(e.target.value)}
                  onFocus={() => handlePanelQuestionFocus(turnIdx)}
                  onBlur={() => { if (editingPanelTurnIndex === turnIdx) setEditingPanelTurnIndex(null); }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handlePanelQuestionResubmit(turnIdx);
                    }
                  }}
                  rows={editingPanelTurnIndex === turnIdx ? 10 : collapsedRows(editingPanelTurnIndex === turnIdx ? editingPanelValue : (turn.user.content ?? ''))}
                  style={editingPanelTurnIndex !== turnIdx ? { minHeight: `${collapsedMinHeightRem(collapsedRows(turn.user.content ?? ''))}rem` } : undefined}
                  className={`flex-1 min-w-0 text-sm text-gray-700 bg-transparent border-0 rounded-lg py-2 px-3 focus:outline-none focus:ring-0 ${
                    editingPanelTurnIndex === turnIdx
                      ? 'max-h-[15rem] overflow-y-auto resize-none'
                      : 'max-h-[10rem] overflow-hidden resize-none'
                  }`}
                  disabled={disabled}
                  title="Click to expand. Edit and press Enter or click resubmit (Shift+Enter for newline)"
                />
                {onEditAndResubmit && (
                  <button
                    type="button"
                    onClick={() => handlePanelQuestionResubmit(turnIdx)}
                    disabled={disabled || !(editingPanelTurnIndex === turnIdx ? editingPanelValue : turn.user.content ?? '').trim()}
                    className="shrink-0 p-1.5 rounded text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-50"
                    title="Resubmit from this point"
                  >
                    <ReplayIcon sx={{ fontSize: 16 }} />
                  </button>
                )}
              </div>
              {turn.assistants.map((msg, idx) => (
                <AgentMessage
                  key={idx}
                  message={msg}
                  organizationId={organizationId}
                  onApprove={(id) => handleApproveOne(id, true)}
                  onReject={(id) => handleApproveOne(id, false)}
                  onAlwaysApprove={onAlwaysApprove}
                  pendingCallIds={individualPendingIds}
                  disabled={disabled}
                  resolvedToolCalls={resolvedMap}
                  executedOnlyIds={executedOnlyIds}
                  readOnlyTools={readOnlyTools}
                />
              ))}
            </div>
          ))}
          {pendingToolCalls.length > 1 && (
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
          {loading && (() => {
            const last = messages[messages.length - 1];
            const hasAnyAssistantContent = last?.role === 'assistant' && (
              !!last.thinking?.trim() || !!last.content?.trim() || (last.executedRounds?.length ?? 0) > 0
            );
            return !hasAnyAssistantContent && <ThinkingBlock live />;
          })()}
          {error && (
            <div className="rounded-lg px-3 py-2 bg-red-50 border border-red-200 text-red-700 text-xs">
              {error}
            </div>
          )}
          <div ref={endRef} />
          </div>
        </div>
      </div>
    </div>
  );
}
