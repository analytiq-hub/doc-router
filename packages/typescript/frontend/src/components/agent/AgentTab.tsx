'use client';

import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import ArrowCircleUpIcon from '@mui/icons-material/ArrowCircleUp';
import StopCircleIcon from '@mui/icons-material/StopCircle';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import MicIcon from '@mui/icons-material/Mic';
import { useAgentChat, getMessagesBeforeTurn } from './useAgentChat';
import AgentChat from './AgentChat';
import ThreadDropdown from './ThreadDropdown';
import { useDictation } from './useDictation';
import { DocRouterOrgApi } from '@/utils/api';
import { useDocumentPage } from '@/contexts/DocumentPageContext';
import type { AgentThreadSummary } from './useAgentChat';

interface AgentTabProps {
  organizationId: string;
  documentId: string;
}

/** Chat is only enabled when document state is llm_completed. */
function isChatDisabled(state: string | null): boolean {
  return state !== 'llm_completed';
}

export default function AgentTab({ organizationId, documentId }: AgentTabProps) {
  const documentPage = useDocumentPage();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [localDocumentState, setLocalDocumentState] = useState<string | null>(null);

  // When DocumentPageContext provides state, use it (avoids duplicate GET document).
  const documentState = documentPage?.documentState ?? localDocumentState;

  // Only fetch/poll when not using shared context
  useEffect(() => {
    if (documentPage != null) return;
    const fetchState = async () => {
      try {
        try {
          const doc = await docRouterOrgApi.getDocument({ documentId, fileType: 'pdf', includeContent: false });
          setLocalDocumentState(doc.state);
          return;
        } catch {
          // Non-PDF documents may not have pdf; try original
        }
        const doc = await docRouterOrgApi.getDocument({ documentId, fileType: 'original', includeContent: false });
        setLocalDocumentState(doc.state);
      } catch (error) {
        console.error('Error fetching document state:', error);
        setLocalDocumentState(null);
      }
    };
    fetchState();
  }, [documentPage, organizationId, documentId, docRouterOrgApi]);

  useEffect(() => {
    if (documentPage != null || !isChatDisabled(documentState)) return;
    const poll = setInterval(async () => {
      try {
        try {
          const doc = await docRouterOrgApi.getDocument({ documentId, fileType: 'pdf', includeContent: false });
          setLocalDocumentState(doc.state);
          return;
        } catch {
          /* try original */
        }
        const doc = await docRouterOrgApi.getDocument({ documentId, fileType: 'original', includeContent: false });
        setLocalDocumentState(doc.state);
      } catch (error) {
        console.error('Error polling document state:', error);
      }
    }, 2000);
    return () => clearInterval(poll);
  }, [documentPage, documentState, documentId, docRouterOrgApi]);

  const chatDisabled = isChatDisabled(documentState);

  const {
    state,
    sendMessage,
    sendMessageWithHistory,
    approveToolCalls,
    cancelRequest,
    toggleToolAutoApproved,
    addToolToAutoApproved,
    enableAllTools,
    resetToolPermissions,
    loadTools,
    setModel,
    loadModels,
    loadThreads,
    loadThread,
    deleteThread,
    startNewChat,
  } = useAgentChat(organizationId, documentId);

  const [input, setInput] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const interimRef = useRef('');
  const [showModelDropUp, setShowModelDropUp] = useState(false);
  const [showToolsDropUp, setShowToolsDropUp] = useState(false);
  const modelDropRef = useRef<HTMLDivElement>(null);
  const toolsDropRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    displayInputRef.current = displayInput;
  }, [displayInput]);

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

  // Defer models/tools until user opens the dropdowns (avoids blocking initial page Finish)
  useEffect(() => {
    if (showModelDropUp) loadModels();
  }, [showModelDropUp, loadModels]);

  useEffect(() => {
    if (showToolsDropUp) loadTools();
  }, [showToolsDropUp, loadTools]);

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
      const target = e.target as Node;
      if (modelDropRef.current && !modelDropRef.current.contains(target)) {
        setShowModelDropUp(false);
      }
      if (toolsDropRef.current && !toolsDropRef.current.contains(target)) {
        setShowToolsDropUp(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSend = () => {
    const text = displayInput.trim();
    if (!text || state.loading || chatDisabled) return;
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
      {chatDisabled && documentState !== null && (
        <div className="px-3 pt-2 pb-1 text-sm text-amber-700 bg-amber-50 border-b border-amber-200">
          {documentState === 'ocr_failed' || documentState === 'llm_failed'
            ? 'Document processing did not complete. Chat is not available.'
            : 'Document is being processed. Chat will be available once processing is complete.'}
        </div>
      )}
      {dictationError && (
        <div className="px-3 pt-1 text-xs text-amber-600">{dictationError}</div>
      )}
      <div className="px-3 pt-2 pb-1">
        <div className={`rounded-lg border border-gray-300 bg-white min-w-0 ${chatDisabled ? 'opacity-60' : 'focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500'}`}>
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
            placeholder={chatDisabled ? 'Waiting for document processing…' : 'Message the agent…'}
            rows={3}
            className="w-full min-h-[4rem] max-h-[12rem] py-2.5 px-3 text-sm resize-y border-0 focus:outline-none focus:ring-0 overflow-y-auto bg-transparent"
            style={{ scrollbarGutter: 'stable' }}
            disabled={state.loading || chatDisabled}
          />
        </div>
      </div>
      <div className="flex items-center justify-between px-3 pb-2 pt-0 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="relative" ref={modelDropRef}>
            <button
              type="button"
              onClick={() => { setShowModelDropUp((v) => !v); setShowToolsDropUp(false); }}
              className="flex items-center gap-0.5 text-[11px] text-gray-500 hover:text-gray-700 py-0.5"
              title="Model"
            >
              <KeyboardArrowUpIcon sx={{ fontSize: 14 }} className={showModelDropUp ? '' : 'rotate-180'} />
              <span className="max-w-[120px] truncate">{state.model}</span>
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
              </div>
            )}
          </div>
          <div className="relative" ref={toolsDropRef}>
            <button
              type="button"
              onClick={() => { setShowToolsDropUp((v) => !v); setShowModelDropUp(false); }}
              className="flex items-center gap-0.5 text-[11px] text-gray-500 hover:text-gray-700 py-0.5"
              title={state.autoApprovedTools.length > 0 ? `Tools (${state.autoApprovedTools.length} auto-approved)` : 'Tools'}
            >
              <KeyboardArrowUpIcon sx={{ fontSize: 14 }} className={showToolsDropUp ? '' : 'rotate-180'} />
              <span>Tools</span>
              {state.autoApprovedTools.length > 0 && (
                <span className="text-[10px] text-blue-600 font-medium">({state.autoApprovedTools.length})</span>
              )}
            </button>
            {showToolsDropUp && (
              <div
                className={`absolute left-0 z-50 rounded-md border border-gray-200 bg-white shadow-lg py-1 min-w-[200px] max-h-[70vh] overflow-y-auto ${
                  state.messages.length > 0 ? 'bottom-full mb-1' : 'top-full mt-1'
                }`}
              >
                <div className="px-2 pt-1 pb-2 space-y-1">
                  <div className="pt-1">
                    <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1">
                      Auto-approved tools
                      {state.autoApprovedTools.length > 0 && (
                        <span className="ml-1 text-blue-600 normal-case">({state.autoApprovedTools.length})</span>
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
                </div>
              </div>
            )}
          </div>
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
            disabled={chatDisabled}
            className={`flex items-center justify-center w-8 h-8 shrink-0 ${chatDisabled ? 'text-gray-300 cursor-not-allowed' : 'text-gray-700 hover:text-blue-600'}`}
            title="Send"
          >
            <ArrowCircleUpIcon sx={{ fontSize: 24 }} />
          </button>
        ) : dictationSupported && !chatDisabled ? (
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
            onOpen={loadThreads}
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
              approvedCallIds={state.approvedCallIds}
              readOnlyTools={state.readOnlyTools}
              loading={state.loading}
              error={state.error}
              onApprove={handleApprove}
              onAlwaysApprove={addToolToAutoApproved}
              onEditAndResubmit={handleEditAndResubmit}
              disabled={state.loading || chatDisabled}
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
              approvedCallIds={state.approvedCallIds}
              readOnlyTools={state.readOnlyTools}
              loading={state.loading}
              error={state.error}
              onApprove={handleApprove}
              onAlwaysApprove={addToolToAutoApproved}
              onEditAndResubmit={handleEditAndResubmit}
              disabled={state.loading || chatDisabled}
            />
          </div>
        </>
      )}
    </div>
  );
}
