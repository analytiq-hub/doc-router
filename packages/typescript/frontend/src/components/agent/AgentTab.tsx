'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import ArrowCircleUpIcon from '@mui/icons-material/ArrowCircleUp';
import StopCircleIcon from '@mui/icons-material/StopCircle';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import MicIcon from '@mui/icons-material/Mic';
import { useAgentChat, getMessagesBeforeTurn } from './useAgentChat';
import AgentChat from './AgentChat';
import ThreadDropdown from './ThreadDropdown';
import { useDictation } from './useDictation';
import type { AgentThreadSummary } from './useAgentChat';

interface AgentTabProps {
  organizationId: string;
  documentId: string;
}

export default function AgentTab({ organizationId, documentId }: AgentTabProps) {
  const {
    state,
    sendMessage,
    sendMessageWithHistory,
    approveToolCalls,
    cancelRequest,
    setAutoApprove,
    setAutoApprovedTools,
    toggleToolAutoApproved,
    addToolToAutoApproved,
    enableAllTools,
    resetToolPermissions,
    loadTools,
    setModel,
    setError,
    loadModels,
    loadThread,
    deleteThread,
    startNewChat,
  } = useAgentChat(organizationId, documentId);

  const [input, setInput] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const interimRef = useRef('');
  const [showModelDropUp, setShowModelDropUp] = useState(false);
  const modelDropRef = useRef<HTMLDivElement>(null);

  const handleTranscript = useCallback(
    (text: string, isFinal: boolean) => {
      if (isFinal) {
        setInput((prev) => prev + (prev ? ' ' : '') + text);
        interimRef.current = '';
        setInterimTranscript('');
      } else {
        interimRef.current = text;
        setInterimTranscript(text);
      }
    },
    []
  );

  const displayInput = input + (interimTranscript ? (input ? ' ' : '') + interimTranscript : '');
  const hasText = displayInput.trim().length > 0;
  const displayInputRef = useRef(displayInput);
  displayInputRef.current = displayInput;

  const handleDictationEnd = useCallback(() => {
    const text = displayInputRef.current.trim();
    if (text && !state.loading) {
      setInput('');
      setInterimTranscript('');
      interimRef.current = '';
      sendMessage(text);
    }
  }, [sendMessage, state.loading]);

  const { supported: dictationSupported, isListening, toggle: toggleDictation, error: dictationError } = useDictation(
    handleTranscript,
    handleDictationEnd
  );

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  useEffect(() => {
    if (showModelDropUp) loadTools();
  }, [showModelDropUp, loadTools]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === ' ') {
        e.preventDefault();
        if (dictationSupported) toggleDictation();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [dictationSupported, toggleDictation]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modelDropRef.current && !modelDropRef.current.contains(e.target as Node)) {
        setShowModelDropUp(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSend = () => {
    const text = displayInput.trim();
    if (!text || state.loading) return;
    setInput('');
    setInterimTranscript('');
    interimRef.current = '';
    sendMessage(text);
  };

  const handleApprove = (approvals: Array<{ call_id: string; approved: boolean }>) => {
    approveToolCalls(approvals);
  };

  const handleSelectThread = (t: AgentThreadSummary) => {
    if (t.id === state.threadId) return;
    loadThread(t.id);
  };

  const handleEditAndResubmit = (newContent: string, turnIndex: number) => {
    const history = getMessagesBeforeTurn(state.messages, turnIndex);
    sendMessageWithHistory(history, newContent);
  };

  const inputBlock = (
    <div className="shrink-0 border-t border-gray-200 bg-white min-w-0">
      {dictationError && (
        <div className="px-3 pt-1 text-xs text-amber-600">{dictationError}</div>
      )}
      <div className="px-3 pt-2 pb-1">
        <div className="rounded-lg border border-gray-300 bg-white focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500 min-w-0">
          <textarea
            value={displayInput}
            onChange={(e) => {
              setInput(e.target.value);
              setInterimTranscript('');
              interimRef.current = '';
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Message the agent…"
            rows={3}
            className="w-full min-h-[4rem] max-h-[12rem] py-2.5 px-3 text-sm resize-y border-0 focus:outline-none focus:ring-0 overflow-y-auto bg-transparent"
            style={{ scrollbarGutter: 'stable' }}
            disabled={state.loading}
          />
        </div>
      </div>
      <div className="flex items-center justify-between px-3 pb-2 pt-0 gap-2">
        <div className="relative flex items-center gap-2 min-w-0" ref={modelDropRef}>
          <button
            type="button"
            onClick={() => setShowModelDropUp((v) => !v)}
            className="flex items-center gap-0.5 text-[11px] text-gray-500 hover:text-gray-700 py-0.5"
            title={state.autoApprove ? 'Model (all tools auto-approved)' : state.autoApprovedTools.length > 0 ? `Model · ${state.autoApprovedTools.length} tool(s) auto-approved` : 'Model · Tool permissions'}
          >
            <KeyboardArrowUpIcon sx={{ fontSize: 14 }} className={showModelDropUp ? '' : 'rotate-180'} />
            <span className="max-w-[120px] truncate">{state.model}</span>
            {!state.autoApprove && state.autoApprovedTools.length > 0 && (
              <span className="text-[10px] text-blue-600 font-medium">({state.autoApprovedTools.length})</span>
            )}
          </button>
          {showModelDropUp && (
            <div
              className={`absolute left-0 z-50 rounded-md border border-gray-200 bg-white shadow-lg py-1 min-w-[200px] max-h-[70vh] overflow-y-auto ${
                state.messages.length > 0 ? 'bottom-full mb-1' : 'top-full mt-1'
              }`}
            >
              {state.availableModels.length === 0 ? (
                <div className="px-3 py-2 text-xs text-gray-500">Loading models…</div>
              ) : (
                state.availableModels.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => { setModel(m); setShowModelDropUp(false); }}
                    className={`block w-full text-left px-3 py-1.5 text-xs ${m === state.model ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700 hover:bg-gray-50'}`}
                  >
                    {m}
                  </button>
                ))
              )}
              <div className="border-t border-gray-100 mt-1 pt-1 px-2 space-y-1">
                <label className="flex items-center gap-2 text-[11px] text-gray-600 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={state.autoApprove}
                    onChange={(e) => setAutoApprove(e.target.checked)}
                    className="rounded"
                  />
                  Auto-approve all tools
                </label>
                {!state.autoApprove && (
                  <div className="pt-1">
                    <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1">
                      Tool permissions
                      {state.autoApprovedTools.length > 0 && (
                        <span className="ml-1 text-blue-600 normal-case">({state.autoApprovedTools.length} auto-approved)</span>
                      )}
                    </div>
                    <div className="flex gap-1 mb-1">
                      <button
                        type="button"
                        onClick={() => enableAllTools()}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 hover:bg-gray-200 text-gray-700"
                      >
                        Enable all
                      </button>
                      <button
                        type="button"
                        onClick={resetToolPermissions}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 hover:bg-gray-200 text-gray-700"
                      >
                        Reset to default
                      </button>
                    </div>
                    <div className="max-h-32 overflow-y-auto space-y-0.5">
                      {state.readWriteTools.map((name) => (
                        <label key={name} className="flex items-center gap-1.5 text-[11px] text-gray-600 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={state.autoApprovedTools.includes(name)}
                            onChange={() => toggleToolAutoApproved(name)}
                            className="rounded"
                          />
                          <span className="truncate">{name}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
        {state.loading ? (
          <button
            type="button"
            onClick={cancelRequest}
            className="flex items-center justify-center w-8 h-8 text-red-500 hover:text-red-700 shrink-0"
            title="Stop"
          >
            <StopCircleIcon sx={{ fontSize: 24 }} />
          </button>
        ) : isListening ? (
          <button
            type="button"
            onClick={toggleDictation}
            className="flex items-center justify-center w-8 h-8 text-blue-600 hover:text-blue-700 shrink-0 animate-pulse ring-2 ring-blue-400/50 rounded-full"
            title="Click to send"
          >
            <ArrowCircleUpIcon sx={{ fontSize: 24 }} />
          </button>
        ) : hasText ? (
          <button
            type="button"
            onClick={handleSend}
            className="flex items-center justify-center w-8 h-8 text-gray-700 hover:text-blue-600 shrink-0"
            title="Send"
          >
            <ArrowCircleUpIcon sx={{ fontSize: 24 }} />
          </button>
        ) : dictationSupported ? (
          <button
            type="button"
            onClick={toggleDictation}
            className="flex items-center justify-center w-8 h-8 text-gray-500 hover:text-gray-700 shrink-0"
            title="Voice input (Ctrl+Shift+Space)"
          >
            <MicIcon sx={{ fontSize: 24 }} />
          </button>
        ) : (
          <button
            type="button"
            disabled
            className="flex items-center justify-center w-8 h-8 text-gray-300 cursor-not-allowed shrink-0"
            title="Send"
          >
            <ArrowCircleUpIcon sx={{ fontSize: 24 }} />
          </button>
        )}
      </div>
    </div>
  );

  const hasMessages = state.messages.length > 0;

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
      ) : hasMessages ? (
        <>
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <AgentChat
              organizationId={organizationId}
              messages={state.messages}
              pendingToolCalls={state.pendingToolCalls}
              loading={state.loading}
              error={state.error}
              onApprove={handleApprove}
              onAlwaysApprove={addToolToAutoApproved}
              onEditAndResubmit={handleEditAndResubmit}
              disabled={state.loading}
            />
          </div>
          {inputBlock}
        </>
      ) : (
        <>
          {inputBlock}
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <AgentChat
              organizationId={organizationId}
              messages={state.messages}
              pendingToolCalls={state.pendingToolCalls}
              loading={state.loading}
              error={state.error}
              onApprove={handleApprove}
              onAlwaysApprove={addToolToAutoApproved}
              onEditAndResubmit={handleEditAndResubmit}
              disabled={state.loading}
            />
          </div>
        </>
      )}
    </div>
  );
}
