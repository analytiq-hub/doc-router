'use client';

import React, { useEffect, useState } from 'react';
import SendIcon from '@mui/icons-material/Send';
import SettingsIcon from '@mui/icons-material/Settings';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useAgentChat } from './useAgentChat';
import AgentChat from './AgentChat';
import ExtractionPanel from './ExtractionPanel';
import type { AgentThreadSummary } from './useAgentChat';

interface AgentTabProps {
  organizationId: string;
  documentId: string;
}

function formatThreadDate(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

export default function AgentTab({ organizationId, documentId }: AgentTabProps) {
  const {
    state,
    sendMessage,
    approveToolCalls,
    setAutoApprove,
    setModel,
    setError,
    loadModels,
    loadThread,
    deleteThread,
    startNewChat,
  } = useAgentChat(organizationId, documentId);

  const [input, setInput] = useState('');
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || state.loading) return;
    setInput('');
    sendMessage(text);
  };

  const handleApprove = (approvals: Array<{ call_id: string; approved: boolean }>) => {
    approveToolCalls(approvals);
  };

  const handleSelectThread = (t: AgentThreadSummary) => {
    if (t.id === state.threadId) return;
    loadThread(t.id);
  };

  const handleDeleteThread = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteThread(id);
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Thread list */}
        <div className="w-48 shrink-0 flex flex-col border-r border-gray-200 bg-gray-50">
          <button
            type="button"
            onClick={startNewChat}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 border-b border-gray-200"
          >
            <AddIcon fontSize="small" />
            New chat
          </button>
          <div className="flex-1 overflow-y-auto py-1">
            {state.threadsLoading && state.threads.length === 0 ? (
              <div className="px-3 py-2 text-sm text-gray-500">Loading…</div>
            ) : (
              state.threads.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => handleSelectThread(t)}
                  className={`w-full text-left px-3 py-2 text-sm flex items-center gap-1 group truncate ${
                    state.threadId === t.id
                      ? 'bg-blue-100 text-blue-900'
                      : 'hover:bg-gray-100 text-gray-700'
                  }`}
                >
                  <span className="flex-1 min-w-0 truncate" title={t.title}>
                    {t.title || 'New chat'}
                  </span>
                  <span className="shrink-0 text-xs text-gray-400">{formatThreadDate(t.updated_at)}</span>
                  <button
                    type="button"
                    onClick={(e) => handleDeleteThread(e, t.id)}
                    className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-100 text-gray-500 hover:text-red-600"
                    title="Delete conversation"
                  >
                    <DeleteOutlineIcon sx={{ fontSize: 16 }} />
                  </button>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 min-w-0 flex flex-col">
          {state.threadsLoading && state.messages.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
              Loading conversation…
            </div>
          ) : (
            <>
              <div className="flex-1 min-h-0 flex flex-col">
                <AgentChat
                  messages={state.messages}
                  pendingToolCalls={state.pendingToolCalls}
                  loading={state.loading}
                  error={state.error}
                  onApprove={handleApprove}
                  disabled={state.loading}
                />
              </div>

              <ExtractionPanel extraction={state.extraction} />

              <div className="border-t border-gray-200 p-2 bg-white">
                {showSettings && (
                  <div className="flex flex-wrap items-center gap-3 mb-2 pb-2 border-b border-gray-100">
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={state.autoApprove}
                        onChange={(e) => setAutoApprove(e.target.checked)}
                        className="rounded"
                      />
                      Auto-approve tool calls
                    </label>
                    {state.availableModels.length > 0 && (
                      <label className="flex items-center gap-2 text-sm">
                        Model:
                        <select
                          value={state.model}
                          onChange={(e) => setModel(e.target.value)}
                          className="rounded border border-gray-300 text-sm py-1 px-2"
                        >
                          {state.availableModels.map((m) => (
                            <option key={m} value={m}>
                              {m}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                  </div>
                )}
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setShowSettings((s) => !s)}
                    className="p-1.5 rounded text-gray-500 hover:bg-gray-100"
                    title="Settings"
                  >
                    <SettingsIcon fontSize="small" />
                  </button>
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                    placeholder="Message the agent…"
                    className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    disabled={state.loading}
                  />
                  <button
                    type="button"
                    onClick={handleSend}
                    disabled={!input.trim() || state.loading}
                    className="p-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Send"
                  >
                    <SendIcon fontSize="small" />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
