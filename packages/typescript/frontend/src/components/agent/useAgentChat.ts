'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { apiClient, getApiErrorMsg } from '@/utils/api';

export interface AgentChatMessage {
  role: 'user' | 'assistant';
  content: string | null;
  toolCalls?: PendingToolCall[];
}

export interface PendingToolCall {
  id: string;
  name: string;
  arguments: string;
  approved?: boolean;
}

export interface AgentThreadSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface AgentChatState {
  messages: AgentChatMessage[];
  pendingTurnId: string | null;
  pendingToolCalls: PendingToolCall[];
  /** Latest extraction from working_state (after run_extraction or from approve round). */
  extraction: Record<string, unknown> | null;
  loading: boolean;
  error: string | null;
  autoApprove: boolean;
  model: string;
  availableModels: string[];
  /** Current thread id (null = new unsaved chat). */
  threadId: string | null;
  /** List of threads for this document. */
  threads: AgentThreadSummary[];
  /** Loading threads list or a single thread. */
  threadsLoading: boolean;
}

const DEFAULT_MODEL = 'claude-sonnet-4-5-20250929';

/**
 * Returns messages that come before the given turn index (turns 0..turnIndex-1 only).
 * Used when resubmitting from a turn: we pass only this context to the API so the model
 * never sees the reasked question or any answers after it (newer answers are dropped).
 */
export function getMessagesBeforeTurn(messages: AgentChatMessage[], turnIndex: number): AgentChatMessage[] {
  if (turnIndex <= 0) return [];
  let userCount = 0;
  for (let i = 0; i < messages.length; i++) {
    if (messages[i].role === 'user') {
      if (userCount === turnIndex) return messages.slice(0, i);
      userCount++;
    }
  }
  return messages.slice(0, messages.length);
}

function getChatUrl(organizationId: string, documentId: string, path: string) {
  const base = `/v0/orgs/${organizationId}/documents/${documentId}`;
  return path === 'threads' ? `${base}/chat/threads` : `${base}/${path}`;
}

/** Normalize API message to frontend shape; tool_calls may be { id, name, arguments } or { id, type, function }. */
function messageFromApi(m: { role: string; content?: string | null; tool_calls?: Array<{ id: string; name?: string; arguments?: string; function?: { name: string; arguments: string } }> }): AgentChatMessage {
  const toolCalls = m.tool_calls?.map((tc) => ({
    id: tc.id,
    name: tc.name ?? tc.function?.name ?? '',
    arguments: tc.arguments ?? tc.function?.arguments ?? '{}',
  }));
  return {
    role: m.role as 'user' | 'assistant',
    content: m.content ?? null,
    toolCalls: toolCalls?.length ? toolCalls : undefined,
  };
}

export function useAgentChat(organizationId: string, documentId: string) {
  const [messages, setMessages] = useState<AgentChatMessage[]>([]);
  const [pendingTurnId, setPendingTurnId] = useState<string | null>(null);
  const [pendingToolCalls, setPendingToolCalls] = useState<PendingToolCall[]>([]);
  const [extraction, setExtraction] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoApprove, setAutoApprove] = useState(false);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [threads, setThreads] = useState<AgentThreadSummary[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const cancelRequest = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setLoading(false);
    setError(null);
    // Remove the pending user message that got no response
    setMessages((prev) => {
      if (prev.length > 0 && prev[prev.length - 1].role === 'user') {
        return prev.slice(0, -1);
      }
      return prev;
    });
  }, []);

  const loadThreads = useCallback(async () => {
    setThreadsLoading(true);
    try {
      const { data } = await apiClient.get<AgentThreadSummary[]>(
        getChatUrl(organizationId, documentId, 'threads')
      );
      setThreads(Array.isArray(data) ? data : []);
    } catch {
      setThreads([]);
    } finally {
      setThreadsLoading(false);
    }
  }, [organizationId, documentId]);

  const loadThread = useCallback(
    async (id: string) => {
      setThreadsLoading(true);
      setError(null);
      try {
        const { data } = await apiClient.get<{
          id: string;
          title: string;
          messages: Array<{ role: string; content?: string | null; tool_calls?: Array<{ id: string; name?: string; arguments?: string; function?: { name: string; arguments: string } }> }>;
          extraction: Record<string, unknown>;
        }>(`${getChatUrl(organizationId, documentId, 'threads')}/${id}`);
        setThreadId(data.id);
        setMessages((data.messages ?? []).map(messageFromApi));
        setExtraction(data.extraction && Object.keys(data.extraction).length > 0 ? data.extraction : null);
        setPendingTurnId(null);
        setPendingToolCalls([]);
      } catch (err) {
        setError(getApiErrorMsg(err) ?? 'Failed to load conversation');
      } finally {
        setThreadsLoading(false);
      }
    },
    [organizationId, documentId]
  );

  const createThread = useCallback(async (): Promise<string | null> => {
    try {
      const { data } = await apiClient.post<{ thread_id: string }>(
        getChatUrl(organizationId, documentId, 'threads'),
        {}
      );
      const id = data.thread_id;
      setThreads((prev) => [{ id, title: 'New chat', created_at: new Date().toISOString(), updated_at: new Date().toISOString() }, ...prev]);
      return id;
    } catch {
      return null;
    }
  }, [organizationId, documentId]);

  const deleteThread = useCallback(
    async (id: string) => {
      try {
        await apiClient.delete(`${getChatUrl(organizationId, documentId, 'threads')}/${id}`);
        setThreads((prev) => prev.filter((t) => t.id !== id));
        if (threadId === id) {
          setThreadId(null);
          setMessages([]);
          setExtraction(null);
          setPendingTurnId(null);
          setPendingToolCalls([]);
        }
      } catch (err) {
        setError(getApiErrorMsg(err) ?? 'Failed to delete conversation');
      }
    },
    [organizationId, documentId, threadId]
  );

  const startNewChat = useCallback(() => {
    setThreadId(null);
    setMessages([]);
    setExtraction(null);
    setPendingTurnId(null);
    setPendingToolCalls([]);
    setError(null);
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || loading) return;

      let currentThreadId = threadId;
      if (!currentThreadId) {
        const newId = await createThread();
        if (!newId) {
          setError('Failed to create conversation');
          return;
        }
        currentThreadId = newId;
        setThreadId(newId);
      }

      const userMsg: AgentChatMessage = { role: 'user', content: content.trim() };
      setMessages((prev) => [...prev, userMsg]);
      setError(null);
      setLoading(true);
      const controller = new AbortController();
      abortRef.current = controller;

      const messageListForApi = [
        ...messages.map((m) => ({
          role: m.role,
          content: m.content ?? '',
          ...(m.toolCalls?.length && {
            tool_calls: m.toolCalls.map((tc) => ({
              id: tc.id,
              type: 'function' as const,
              function: { name: tc.name, arguments: tc.arguments },
            })),
          }),
        })),
        { role: 'user' as const, content: content.trim() },
      ];

      try {
        const { data } = await apiClient.post<{
          text?: string;
          turn_id?: string;
          tool_calls?: Array<{ id: string; name: string; arguments: string }>;
          working_state?: { extraction?: Record<string, unknown> };
        }>(getChatUrl(organizationId, documentId, 'chat'), {
          messages: messageListForApi,
          mentions: [],
          model,
          stream: false,
          auto_approve: autoApprove,
          thread_id: currentThreadId,
        }, { signal: controller.signal });

        if (data.working_state?.extraction != null) {
          setExtraction(data.working_state.extraction);
        }

        const assistantMsg: AgentChatMessage = {
          role: 'assistant',
          content: data.text ?? null,
          toolCalls: data.tool_calls?.map((tc) => ({ id: tc.id, name: tc.name, arguments: tc.arguments })) ?? undefined,
        };
        setMessages((prev) => [...prev, assistantMsg]);

        if (data.turn_id && data.tool_calls?.length) {
          setPendingTurnId(data.turn_id);
          setPendingToolCalls(
            data.tool_calls.map((tc) => ({ id: tc.id, name: tc.name, arguments: tc.arguments }))
          );
        } else {
          setPendingTurnId(null);
          setPendingToolCalls([]);
        }
        await loadThreads();
      } catch (err) {
        if (controller.signal.aborted) return;
        const msg = getApiErrorMsg(err) ?? 'Failed to send message';
        setError(msg);
        setMessages((prev) => prev.slice(0, -1));
      } finally {
        abortRef.current = null;
        setLoading(false);
      }
    },
    [organizationId, documentId, messages, model, autoApprove, loading, threadId, createThread, loadThreads]
  );

  /** Send a new message with a specific history (e.g. after editing and resubmitting from a prior turn). Truncates conversation to history then sends content. */
  const sendMessageWithHistory = useCallback(
    async (history: AgentChatMessage[], content: string) => {
      if (!content.trim() || loading) return;

      const trimmed = content.trim();
      let currentThreadId = threadId;
      if (!currentThreadId) {
        const newId = await createThread();
        if (!newId) {
          setError('Failed to create conversation');
          return;
        }
        currentThreadId = newId;
        setThreadId(newId);
      }

      const userMsg: AgentChatMessage = { role: 'user', content: trimmed };
      setMessages([...history, userMsg]);
      setError(null);
      setLoading(true);
      const controller = new AbortController();
      abortRef.current = controller;

      const messageListForApi = [
        ...history.map((m) => ({
          role: m.role,
          content: m.content ?? '',
          ...(m.toolCalls?.length && {
            tool_calls: m.toolCalls.map((tc) => ({
              id: tc.id,
              type: 'function' as const,
              function: { name: tc.name, arguments: tc.arguments },
            })),
          }),
        })),
        { role: 'user' as const, content: trimmed },
      ];

      const body: Record<string, unknown> = {
        messages: messageListForApi,
        mentions: [],
        model,
        stream: false,
        auto_approve: autoApprove,
        thread_id: currentThreadId,
      };
      if (currentThreadId && history.length > 0) {
        body.truncate_thread_to_message_count = history.length;
      }

      try {
        const { data } = await apiClient.post<{
          text?: string;
          turn_id?: string;
          tool_calls?: Array<{ id: string; name: string; arguments: string }>;
          working_state?: { extraction?: Record<string, unknown> };
        }>(getChatUrl(organizationId, documentId, 'chat'), body, { signal: controller.signal });

        if (data.working_state?.extraction != null) {
          setExtraction(data.working_state.extraction);
        }

        const assistantMsg: AgentChatMessage = {
          role: 'assistant',
          content: data.text ?? null,
          toolCalls: data.tool_calls?.map((tc) => ({ id: tc.id, name: tc.name, arguments: tc.arguments })) ?? undefined,
        };
        setMessages((prev) => [...prev, assistantMsg]);

        if (data.turn_id && data.tool_calls?.length) {
          setPendingTurnId(data.turn_id);
          setPendingToolCalls(
            data.tool_calls.map((tc) => ({ id: tc.id, name: tc.name, arguments: tc.arguments }))
          );
        } else {
          setPendingTurnId(null);
          setPendingToolCalls([]);
        }
        await loadThreads();
      } catch (err) {
        if (controller.signal.aborted) return;
        const msg = getApiErrorMsg(err) ?? 'Failed to send message';
        setError(msg);
        setMessages([...history]);
      } finally {
        abortRef.current = null;
        setLoading(false);
      }
    },
    [organizationId, documentId, model, autoApprove, loading, threadId, createThread, loadThreads]
  );

  const approveToolCalls = useCallback(
    async (approvals: Array<{ call_id: string; approved: boolean }>) => {
      if (!pendingTurnId || loading) return;

      setLoading(true);
      setError(null);
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const { data } = await apiClient.post<{
          text?: string;
          turn_id?: string;
          tool_calls?: Array<{ id: string; name: string; arguments: string }>;
          working_state?: { extraction?: Record<string, unknown> };
        }>(getChatUrl(organizationId, documentId, 'chat/approve'), {
          turn_id: pendingTurnId,
          approvals,
          thread_id: threadId ?? undefined,
        }, { signal: controller.signal });

        if (data.working_state?.extraction != null) {
          setExtraction(data.working_state.extraction);
        }

        setPendingTurnId(null);
        setPendingToolCalls([]);

        const assistantMsg: AgentChatMessage = {
          role: 'assistant',
          content: data.text ?? null,
          toolCalls: data.tool_calls?.map((tc) => ({ id: tc.id, name: tc.name, arguments: tc.arguments })) ?? undefined,
        };
        setMessages((prev) => [...prev, assistantMsg]);

        if (data.turn_id && data.tool_calls?.length) {
          setPendingTurnId(data.turn_id);
          setPendingToolCalls(
            data.tool_calls.map((tc) => ({ id: tc.id, name: tc.name, arguments: tc.arguments }))
          );
        }
        if (threadId) await loadThreads();
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(getApiErrorMsg(err) ?? 'Failed to submit approvals');
      } finally {
        abortRef.current = null;
        setLoading(false);
      }
    },
    [organizationId, documentId, pendingTurnId, loading, threadId, loadThreads]
  );

  const loadModels = useCallback(async () => {
    try {
      const { data } = await apiClient.get<{ models: string[] }>(
        `/v0/orgs/${organizationId}/llm/models`
      );
      setAvailableModels(data.models ?? []);
      if (data.models?.length && !data.models.includes(model)) {
        setModel(data.models[0]);
      }
    } catch {
      // optional; keep default model
    }
  }, [organizationId, model]);

  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  const state: AgentChatState = {
    messages,
    pendingTurnId,
    pendingToolCalls,
    extraction,
    loading,
    error,
    autoApprove,
    model,
    availableModels,
    threadId,
    threads,
    threadsLoading,
  };

  return {
    state,
    sendMessage,
    sendMessageWithHistory,
    approveToolCalls,
    cancelRequest,
    setAutoApprove,
    setModel,
    setError,
    loadModels,
    loadThreads,
    loadThread,
    createThread,
    deleteThread,
    startNewChat,
  };
}
