'use client';

import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { apiClient, getApiErrorMsg, getSessionToken } from '@/utils/api';

const API_BASE = typeof process !== 'undefined' ? (process.env.NEXT_PUBLIC_FASTAPI_FRONTEND_URL || 'http://localhost:8000') : 'http://localhost:8000';

export interface ExecutedRound {
  thinking?: string | null;
  tool_calls?: Array<{ id: string; name: string; arguments: string }>;
}

function normalizeExecutedRounds(
  rounds?: Array<{ thinking?: string | null; tool_calls?: Array<{ id: string; name?: string; arguments?: string }> }> | null
): ExecutedRound[] | undefined {
  if (!rounds?.length) return undefined;
  return rounds.map((r) => ({
    thinking: r.thinking ?? null,
    tool_calls: r.tool_calls?.map((tc) => ({
      id: tc.id,
      name: tc.name ?? '',
      arguments: tc.arguments ?? '{}',
    })),
  }));
}

export interface AgentChatMessage {
  role: 'user' | 'assistant';
  content: string | null;
  toolCalls?: PendingToolCall[];
  /** Extended thinking/reasoning from the model (Cursor-style). */
  thinking?: string | null;
  /** Rounds that were auto-executed (thinking + tool_calls). */
  executedRounds?: ExecutedRound[];
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
  /** Call IDs we've approved/rejected this session; merged with message-based resolution. */
  approvedCallIds: Map<string, boolean>;
  /** Latest extraction from working_state (after run_extraction or from approve round). */
  extraction: Record<string, unknown> | null;
  loading: boolean;
  error: string | null;
  autoApprove: boolean;
  /** Read-write tool names that are auto-approved when autoApprove is false. Empty = default. */
  autoApprovedTools: string[];
  model: string;
  availableModels: string[];
  /** Read-write tools from API (for tool permissions UI). */
  readWriteTools: string[];
  /** Read-only tools from API (always auto-approved; no approval UI). */
  readOnlyTools: string[];
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
  if (path === 'threads') return `${base}/chat/threads`;
  if (path === 'tools') return `${base}/chat/tools`;
  return `${base}/${path}`;
}

const AUTO_APPROVED_TOOLS_KEY = 'agent-auto-approved-tools';

function loadAutoApprovedToolsFromStorage(organizationId: string, documentId: string): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(`${AUTO_APPROVED_TOOLS_KEY}-${organizationId}-${documentId}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.every((x) => typeof x === 'string') ? parsed : [];
  } catch {
    return [];
  }
}

function saveAutoApprovedToolsToStorage(organizationId: string, documentId: string, tools: string[]) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(`${AUTO_APPROVED_TOOLS_KEY}-${organizationId}-${documentId}`, JSON.stringify(tools));
  } catch {
    // ignore
  }
}

/** Normalize API message to frontend shape; tool_calls may be { id, name, arguments } or { id, type, function }. */
function messageFromApi(m: {
  role: string;
  content?: string | null;
  tool_calls?: Array<{ id: string; name?: string; arguments?: string; function?: { name: string; arguments: string }; approved?: boolean }>;
  thinking?: string | null;
  executed_rounds?: ExecutedRound[] | null;
}): AgentChatMessage {
  const toolCalls = m.tool_calls?.map((tc) => ({
    id: tc.id,
    name: tc.name ?? tc.function?.name ?? '',
    arguments: tc.arguments ?? tc.function?.arguments ?? '{}',
    ...(tc.approved !== undefined && { approved: tc.approved }),
  }));
  const executedRounds = normalizeExecutedRounds(m.executed_rounds);
  return {
    role: m.role as 'user' | 'assistant',
    content: m.content ?? null,
    toolCalls: toolCalls?.length ? toolCalls : undefined,
    thinking: m.thinking ?? undefined,
    executedRounds: executedRounds?.length ? executedRounds : undefined,
  };
}

export function useAgentChat(organizationId: string, documentId: string) {
  const [messages, setMessages] = useState<AgentChatMessage[]>([]);
  const [pendingTurnId, setPendingTurnId] = useState<string | null>(null);
  const [pendingToolCalls, setPendingToolCalls] = useState<PendingToolCall[]>([]);
  const [approvedCallIds, setApprovedCallIds] = useState<Map<string, boolean>>(new Map());
  const [extraction, setExtraction] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoApprove, setAutoApprove] = useState(false);
  /** Refresh key to re-read from localStorage; source of truth is browser storage, not React state */
  const [autoApprovedToolsRefresh, setAutoApprovedToolsRefresh] = useState(0);
  const autoApprovedTools = useMemo(
    () => loadAutoApprovedToolsFromStorage(organizationId, documentId),
    [organizationId, documentId, autoApprovedToolsRefresh]
  );
  const setAutoApprovedTools = useCallback(
    (updater: string[] | ((prev: string[]) => string[])) => {
      const current = loadAutoApprovedToolsFromStorage(organizationId, documentId);
      const next = typeof updater === 'function' ? updater(current) : updater;
      saveAutoApprovedToolsToStorage(organizationId, documentId, next);
      setAutoApprovedToolsRefresh((k) => k + 1);
    },
    [organizationId, documentId]
  );
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [readWriteTools, setReadWriteTools] = useState<string[]>([]);
  const [readOnlyTools, setReadOnlyTools] = useState<string[]>([]);
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
          messages: Array<{
            role: string;
            content?: string | null;
            tool_calls?: Array<{ id: string; name?: string; arguments?: string; function?: { name: string; arguments: string } }>;
            thinking?: string | null;
            executed_rounds?: ExecutedRound[] | null;
          }>;
          extraction: Record<string, unknown>;
          model?: string | null;
        }>(`${getChatUrl(organizationId, documentId, 'threads')}/${id}`);
        setThreadId(data.id);
        setMessages((data.messages ?? []).map(messageFromApi));
        setExtraction(data.extraction && Object.keys(data.extraction).length > 0 ? data.extraction : null);
        setModel(data.model && data.model.trim() ? data.model : DEFAULT_MODEL);
        setPendingTurnId(null);
        setPendingToolCalls([]);
        setApprovedCallIds(new Map());
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
          setApprovedCallIds(new Map());
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
    setApprovedCallIds(new Map());
    setError(null);
  }, []);

  /** Shared streaming chat: POST with stream: true, parse SSE, update state. Caller must have already appended the user message. */
  const runStreamingChat = useCallback(
    async (
      body: Record<string, unknown>,
      controller: AbortController,
      onErrorRollback?: () => void
    ): Promise<void> => {
      const placeholder: AgentChatMessage = {
        role: 'assistant',
        content: '',
        thinking: undefined,
        executedRounds: undefined,
      };
      setMessages((prev) => [...prev, placeholder]);
      let hadError = false;
      try {
        const token = await getSessionToken();
        const url = `${API_BASE}${getChatUrl(organizationId, documentId, 'chat')}`;
        const res = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            Accept: 'text/event-stream',
            'Cache-Control': 'no-cache',
          },
          body: JSON.stringify(body),
          signal: controller.signal,
          credentials: 'include',
        });
        if (!res.ok) {
          const errBody = await res.text();
          let msg = `HTTP ${res.status}`;
          try {
            const j = JSON.parse(errBody);
            if (j.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
          } catch {
            if (errBody) msg = errBody.slice(0, 200);
          }
          throw new Error(msg);
        }
        const reader = res.body?.getReader();
        if (!reader) throw new Error('No response body');
        const decoder = new TextDecoder();
        let buffer = '';
        let streamDone = false;
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';
            for (const line of lines) {
              if (!line.startsWith('data: ')) continue;
              try {
                const data = JSON.parse(line.slice(6)) as {
                  type?: string;
                  error?: string;
                  thinking?: string;
                  chunk?: string;
                  full_text?: string;
                  round_index?: number;
                  tool_calls?: Array<{ id: string; name: string; arguments: string }>;
                  result?: {
                    text?: string;
                    turn_id?: string;
                    tool_calls?: Array<{ id: string; name: string; arguments: string }>;
                    working_state?: { extraction?: Record<string, unknown> };
                    thinking?: string;
                    executed_rounds?: ExecutedRound[] | null;
                  };
                };
                if (data.type === 'error') {
                  setError(data.error ?? 'Request failed');
                  setMessages((prev) => prev.slice(0, -1));
                  hadError = true;
                  streamDone = true;
                  break;
                }
                if (data.type === 'assistant_text_chunk' || data.type === 'text_chunk') {
                  const chunk = data.chunk ?? '';
                  setMessages((prev) => {
                    const next = [...prev];
                    const last = next[next.length - 1];
                    if (last?.role === 'assistant')
                      next[next.length - 1] = { ...last, content: (last.content ?? '') + chunk };
                    return next;
                  });
                }
                if (data.type === 'thinking_chunk') {
                  const chunk = data.chunk ?? '';
                  setMessages((prev) => {
                    const next = [...prev];
                    const last = next[next.length - 1];
                    if (last?.role === 'assistant')
                      next[next.length - 1] = { ...last, thinking: (last.thinking ?? '') + chunk };
                    return next;
                  });
                }
                if (data.type === 'assistant_text_done' && data.full_text !== undefined) {
                  setMessages((prev) => {
                    const next = [...prev];
                    const last = next[next.length - 1];
                    if (last?.role === 'assistant')
                      next[next.length - 1] = { ...last, content: data.full_text ?? last.content ?? '' };
                    return next;
                  });
                }
                if (data.type === 'thinking_done' || data.type === 'thinking') {
                  const thinking = data.thinking ?? null;
                  setMessages((prev) => {
                    const next = [...prev];
                    const last = next[next.length - 1];
                    if (last?.role === 'assistant')
                      next[next.length - 1] = { ...last, thinking: thinking ?? last.thinking ?? null };
                    return next;
                  });
                }
                if (data.type === 'tool_calls' && data.tool_calls) {
                  const round: ExecutedRound = { thinking: null, tool_calls: data.tool_calls };
                  setMessages((prev) => {
                    const next = [...prev];
                    const last = next[next.length - 1];
                    if (last?.role === 'assistant')
                      next[next.length - 1] = {
                        ...last,
                        executedRounds: [...(last.executedRounds ?? []), round],
                      };
                    return next;
                  });
                }
                if (data.type === 'round_executed') {
                  const roundIndex = data.round_index ?? 0;
                  const thinking = data.thinking ?? null;
                  const toolCalls = data.tool_calls ?? [];
                  setMessages((prev) => {
                    const next = [...prev];
                    const last = next[next.length - 1];
                    if (last?.role === 'assistant' && last.executedRounds?.length) {
                      const rounds = [...last.executedRounds];
                      if (rounds[roundIndex] != null)
                        rounds[roundIndex] = { thinking, tool_calls: toolCalls };
                      else
                        rounds.push({ thinking, tool_calls: toolCalls });
                      next[next.length - 1] = { ...last, executedRounds: rounds };
                    }
                    return next;
                  });
                }
                if (data.type === 'done' && data.result) {
                  const r = data.result;
                  if (r.working_state?.extraction != null) setExtraction(r.working_state.extraction);
                  setMessages((prev) => {
                    const next = [...prev];
                    const last = next[next.length - 1];
                    if (last?.role === 'assistant')
                      next[next.length - 1] = {
                        ...last,
                        content: r.text ?? last.content ?? null,
                        thinking: r.thinking ?? last.thinking ?? undefined,
                        executedRounds: normalizeExecutedRounds(r.executed_rounds),
                        toolCalls: r.tool_calls?.map((tc) => ({ id: tc.id, name: tc.name, arguments: tc.arguments })),
                      };
                    return next;
                  });
                  if (r.turn_id && r.tool_calls?.length) {
                    setPendingTurnId(r.turn_id);
                    setPendingToolCalls(r.tool_calls.map((tc) => ({ id: tc.id, name: tc.name, arguments: tc.arguments })));
                  } else {
                    setPendingTurnId(null);
                    setPendingToolCalls([]);
                  }
                  streamDone = true;
                  break;
                }
              } catch {
                // ignore malformed SSE line
              }
            }
            if (streamDone) break;
          }
        } finally {
          reader.releaseLock();
        }
        if (!hadError) await loadThreads();
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(getApiErrorMsg(err) ?? 'Failed to send message');
        if (onErrorRollback) onErrorRollback();
        else setMessages((prev) => prev.slice(0, -1));
      }
    },
    [organizationId, documentId, loadThreads]
  );

  const sendMessage = useCallback(
    async (content: string, mentions: Array<{ type: string; id: string }> = []) => {
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

      const body: Record<string, unknown> = {
        messages: messageListForApi,
        mentions: mentions.map((m) => ({ type: m.type, id: m.id })),
        model,
        stream: true,
        auto_approve: autoApprove,
        auto_approved_tools: autoApprove ? undefined : autoApprovedTools,
        thread_id: currentThreadId,
      };

      try {
        await runStreamingChat(body, controller);
      } finally {
        abortRef.current = null;
        setLoading(false);
      }
    },
    [organizationId, documentId, messages, model, autoApprove, autoApprovedTools, loading, threadId, createThread, runStreamingChat]
  );

  /** Send a new message with a specific history (e.g. after editing and resubmitting from a prior turn). Truncates conversation to history then sends content. Uses streaming like sendMessage. */
  const sendMessageWithHistory = useCallback(
    async (history: AgentChatMessage[], content: string, mentions: Array<{ type: string; id: string }> = []) => {
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
        mentions: mentions.map((m) => ({ type: m.type, id: m.id })),
        model,
        stream: true,
        auto_approve: autoApprove,
        auto_approved_tools: autoApprove ? undefined : autoApprovedTools,
        thread_id: currentThreadId,
      };
      if (currentThreadId && history.length > 0) {
        body.truncate_thread_to_message_count = history.length;
      }

      try {
        await runStreamingChat(body, controller, () => setMessages([...history]));
      } finally {
        abortRef.current = null;
        setLoading(false);
      }
    },
    [organizationId, documentId, model, autoApprove, autoApprovedTools, loading, threadId, createThread, runStreamingChat]
  );

  const approveToolCalls = useCallback(
    async (approvals: Array<{ call_id: string; approved: boolean }>) => {
      if (!pendingTurnId || loading) return;

      const approvalsMap = new Map(approvals.map((a) => [a.call_id, a.approved]));
      setApprovedCallIds((prev) => {
        const next = new Map(prev);
        approvalsMap.forEach((v, k) => next.set(k, v));
        return next;
      });

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
          thinking?: string;
          executed_rounds?: ExecutedRound[] | null;
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
          thinking: data.thinking ?? undefined,
          executedRounds: normalizeExecutedRounds(data.executed_rounds),
        };
        setMessages((prev) => {
          const updated = prev.map((msg) => {
            if (msg.role !== 'assistant' || !msg.toolCalls?.length) return msg;
            const hasAnyToUpdate = msg.toolCalls.some((tc) => approvalsMap.has(tc.id));
            if (!hasAnyToUpdate) return msg;
            return {
              ...msg,
              toolCalls: msg.toolCalls.map((tc) => {
                const a = approvalsMap.get(tc.id);
                if (a === undefined) return tc;
                return { ...tc, approved: a };
              }),
            };
          });
          return [...updated, assistantMsg];
        });

        if (data.turn_id && data.tool_calls?.length) {
          setPendingTurnId(data.turn_id);
          setPendingToolCalls(
            data.tool_calls.map((tc) => ({ id: tc.id, name: tc.name, arguments: tc.arguments }))
          );
        }
        if (threadId) await loadThreads();
      } catch (err) {
        if (controller.signal.aborted) return;
        setApprovedCallIds((prev) => {
          const next = new Map(prev);
          approvalsMap.forEach((_, k) => next.delete(k));
          return next;
        });
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

  const loadTools = useCallback(async (): Promise<string[]> => {
    try {
      const { data } = await apiClient.get<{ read_only: string[]; read_write: string[] }>(
        getChatUrl(organizationId, documentId, 'tools')
      );
      const tools = data.read_write ?? [];
      setReadWriteTools(tools);
      setReadOnlyTools(data.read_only ?? []);
      return tools;
    } catch {
      setReadWriteTools([]);
      setReadOnlyTools([]);
      return [];
    }
  }, [organizationId, documentId]);

  const toggleToolAutoApproved = useCallback((toolName: string) => {
    setAutoApprovedTools((prev) =>
      prev.includes(toolName) ? prev.filter((t) => t !== toolName) : [...prev, toolName]
    );
  }, []);

  const enableAllTools = useCallback(async () => {
    const tools = await loadTools();
    if (tools.length) setAutoApprovedTools([...tools]);
  }, [loadTools]);

  const resetToolPermissions = useCallback(() => {
    setAutoApprovedTools([]);
  }, []);

  const addToolToAutoApproved = useCallback((toolName: string) => {
    setAutoApprovedTools((prev) => (prev.includes(toolName) ? prev : [...prev, toolName]));
  }, []);

  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  useEffect(() => {
    loadTools();
  }, [loadTools]);

  const state: AgentChatState = {
    messages,
    pendingTurnId,
    pendingToolCalls,
    approvedCallIds,
    extraction,
    loading,
    error,
    autoApprove,
    autoApprovedTools,
    model,
    availableModels,
    readWriteTools,
    readOnlyTools,
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
    setAutoApprovedTools,
    toggleToolAutoApproved,
    enableAllTools,
    resetToolPermissions,
    addToolToAutoApproved,
    loadTools,
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
