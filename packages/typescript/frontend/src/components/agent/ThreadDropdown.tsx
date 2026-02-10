'use client';

import React, { useState, useRef, useEffect } from 'react';
import HistoryIcon from '@mui/icons-material/History';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import type { AgentThreadSummary } from './useAgentChat';

interface ThreadDropdownProps {
  threads: AgentThreadSummary[];
  threadId: string | null;
  threadsLoading: boolean;
  onSelectThread: (t: AgentThreadSummary) => void;
  onNewChat: () => void;
  onDeleteThread: (id: string) => void;
  /** Optional trigger label when no thread selected */
  newChatLabel?: string;
}

function relativeTime(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const sec = Math.floor((now.getTime() - d.getTime()) / 1000);
    if (sec < 60) return 'now';
    if (sec < 3600) return `${Math.floor(sec / 60)}m`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}h`;
    if (sec < 604800) return `${Math.floor(sec / 86400)}d`;
    if (sec < 2592000) return `${Math.floor(sec / 604800)}w`;
    return `${Math.floor(sec / 2592000)}mo`;
  } catch {
    return '';
  }
}

type GroupKey = 'today' | 'yesterday' | 'week' | 'older';

function getGroupKey(iso: string): GroupKey {
  try {
    const d = new Date(iso);
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const startOfYesterday = new Date(startOfToday);
    startOfYesterday.setDate(startOfYesterday.getDate() - 1);
    const startOfWeek = new Date(startOfToday);
    startOfWeek.setDate(startOfWeek.getDate() - 7);
    if (d >= startOfToday) return 'today';
    if (d >= startOfYesterday) return 'yesterday';
    if (d >= startOfWeek) return 'week';
    return 'older';
  } catch {
    return 'older';
  }
}

const GROUP_LABELS: Record<GroupKey, string> = {
  today: 'Today',
  yesterday: 'Yesterday',
  week: 'This week',
  older: 'Older',
};

function groupThreads(threads: AgentThreadSummary[]): Array<{ key: GroupKey; threads: AgentThreadSummary[] }> {
  const groups: Record<GroupKey, AgentThreadSummary[]> = {
    today: [],
    yesterday: [],
    week: [],
    older: [],
  };
  for (const t of threads) {
    const key = getGroupKey(t.updated_at);
    groups[key].push(t);
  }
  const order: GroupKey[] = ['today', 'yesterday', 'week', 'older'];
  return order.map((key) => ({ key, threads: groups[key] })).filter((g) => g.threads.length > 0);
}

export default function ThreadDropdown({
  threads,
  threadId,
  threadsLoading,
  onSelectThread,
  onNewChat,
  onDeleteThread,
  newChatLabel = 'New chat',
}: ThreadDropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentThread = threadId ? threads.find((t) => t.id === threadId) : null;
  const triggerLabel = currentThread ? (currentThread.title || newChatLabel) : newChatLabel;
  const triggerSub = currentThread ? relativeTime(currentThread.updated_at) : '';

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 px-2 py-1.5 rounded border border-gray-300 bg-white text-sm text-gray-700 hover:bg-gray-50 min-w-0 max-w-[200px]"
        title="Conversation history"
      >
        <HistoryIcon sx={{ fontSize: 18 }} className="shrink-0 text-gray-500" />
        <span className="truncate">{triggerLabel}</span>
        {triggerSub && (
          <span className="shrink-0 text-xs text-gray-400">{triggerSub}</span>
        )}
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 w-72 max-h-80 overflow-hidden flex flex-col rounded-lg border border-gray-200 bg-white shadow-lg">
          <div className="p-1.5 border-b border-gray-100">
            <button
              type="button"
              onClick={() => { onNewChat(); setOpen(false); }}
              className="flex items-center gap-2 w-full px-2 py-2 text-sm text-blue-600 hover:bg-blue-50 rounded"
            >
              <AddIcon fontSize="small" />
              {newChatLabel}
            </button>
          </div>
          <div className="overflow-y-auto flex-1 py-1">
            {threadsLoading && threads.length === 0 ? (
              <div className="px-3 py-4 text-sm text-gray-500 text-center">Loading…</div>
            ) : threads.length === 0 ? (
              <div className="px-3 py-4 text-sm text-gray-500 text-center">No past conversations</div>
            ) : (
              groupThreads(threads).map(({ key, threads: group }) => (
                <div key={key} className="mb-1">
                  <div className="px-3 py-1 text-xs font-medium text-gray-500 uppercase tracking-wide">
                    {GROUP_LABELS[key]}
                  </div>
                  {group.map((t) => (
                    <div
                      key={t.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => { onSelectThread(t); setOpen(false); }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          onSelectThread(t);
                          setOpen(false);
                        }
                      }}
                      className={`flex items-center gap-2 w-full px-3 py-2 text-left text-sm group cursor-pointer ${
                        t.id === threadId ? 'bg-blue-50 text-blue-900' : 'hover:bg-gray-50 text-gray-700'
                      }`}
                    >
                      <span className="flex-1 min-w-0 truncate">{t.title || newChatLabel}</span>
                      <span className="shrink-0 text-xs text-gray-400">{relativeTime(t.updated_at)}</span>
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); onDeleteThread(t.id); }}
                        className="shrink-0 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-100 text-gray-400 hover:text-red-600"
                        title="Delete"
                      >
                        <DeleteOutlineIcon sx={{ fontSize: 16 }} />
                      </button>
                    </div>
                  ))}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
