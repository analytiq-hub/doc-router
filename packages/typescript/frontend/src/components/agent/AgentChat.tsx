'use client';

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import type { AgentChatMessage, PendingToolCall } from './useAgentChat';
import AgentMessage from './AgentMessage';

/** Animated thinking indicator with pulsing dot and elapsed-time counter */
function ThinkingIndicator() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, []);
  return (
    <div className="flex items-center gap-1.5 text-xs text-gray-400 py-1 px-1">
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-gray-400 animate-pulse" />
      <span>Thinking{elapsed > 0 ? ` ${elapsed}s` : ''}</span>
    </div>
  );
}

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
  messages: AgentChatMessage[];
  pendingToolCalls: PendingToolCall[];
  loading: boolean;
  error: string | null;
  onApprove: (approvals: Array<{ call_id: string; approved: boolean }>) => void;
  /** When user edits and resubmits the sticky question, restart conversation from that turn. */
  onEditAndResubmit?: (newContent: string, turnIndex: number) => void;
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
  messages,
  pendingToolCalls,
  loading,
  error,
  onApprove,
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

  const resolvedMap = resolvedFromMessages(messages);
  const pendingIds = pendingCallIds(pendingToolCalls);
  const turns = useMemo(() => messagesToTurns(messages), [messages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const updateStickyQuestion = useCallback(() => {
    const container = scrollRef.current;
    if (!container || turns.length === 0) {
      setStickyQuestion(null);
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
                <ArrowUpwardIcon sx={{ fontSize: 18 }} />
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
                    <ArrowUpwardIcon sx={{ fontSize: 18 }} />
                  </button>
                )}
              </div>
              {turn.assistants.map((msg, idx) => (
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
            </div>
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
          {loading && <ThinkingIndicator />}
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
