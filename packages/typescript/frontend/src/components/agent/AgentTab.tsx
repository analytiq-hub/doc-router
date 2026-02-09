'use client';

import React, { useEffect, useState } from 'react';
import SendIcon from '@mui/icons-material/Send';
import SettingsIcon from '@mui/icons-material/Settings';
import { useAgentChat } from './useAgentChat';
import AgentChat from './AgentChat';
import ThreadDropdown from './ThreadDropdown';
import type { AgentThreadSummary } from './useAgentChat';

interface AgentTabProps {
  organizationId: string;
  documentId: string;
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

  return (
    <div className="flex flex-col h-full min-h-0 bg-white">
      {/* Header: thread dropdown */}
      <div className="shrink-0 flex items-center gap-2 px-2 py-1.5 border-b border-gray-200 bg-gray-50/50">
        <ThreadDropdown
            threads={state.threads}
            threadId={state.threadId}
            threadsLoading={state.threadsLoading}
            onSelectThread={handleSelectThread}
            onNewChat={startNewChat}
            onDeleteThread={deleteThread}
            newChatLabel="New chat"
        />
      </div>

      {state.threadsLoading && state.messages.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
          Loading conversation…
        </div>
      ) : (
        <>
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <AgentChat
              messages={state.messages}
              pendingToolCalls={state.pendingToolCalls}
              loading={state.loading}
              error={state.error}
              onApprove={handleApprove}
              disabled={state.loading}
            />
          </div>

          <div className="shrink-0 border-t border-gray-200 p-2 bg-white">
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
  );
}
