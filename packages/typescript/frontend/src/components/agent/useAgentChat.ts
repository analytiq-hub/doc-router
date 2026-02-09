'use client';

import { useState, useCallback } from 'react';
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
}

const DEFAULT_MODEL = 'claude-sonnet-4-20250514';

function getChatUrl(organizationId: string, documentId: string, path: 'chat' | 'chat/approve') {
  return `/v0/orgs/${organizationId}/documents/${documentId}/${path}`;
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

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || loading) return;

      const userMsg: AgentChatMessage = { role: 'user', content: content.trim() };
      setMessages((prev) => [...prev, userMsg]);
      setError(null);
      setLoading(true);

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
        });

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
      } catch (err) {
        const msg = getApiErrorMsg(err) ?? 'Failed to send message';
        setError(msg);
        setMessages((prev) => prev.slice(0, -1));
      } finally {
        setLoading(false);
      }
    },
    [organizationId, documentId, messages, model, autoApprove, loading]
  );

  const approveToolCalls = useCallback(
    async (approvals: Array<{ call_id: string; approved: boolean }>) => {
      if (!pendingTurnId || loading) return;

      setLoading(true);
      setError(null);

      try {
        const { data } = await apiClient.post<{
          text?: string;
          turn_id?: string;
          tool_calls?: Array<{ id: string; name: string; arguments: string }>;
          working_state?: { extraction?: Record<string, unknown> };
        }>(getChatUrl(organizationId, documentId, 'chat/approve'), {
          turn_id: pendingTurnId,
          approvals,
        });

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
      } catch (err) {
        setError(getApiErrorMsg(err) ?? 'Failed to submit approvals');
      } finally {
        setLoading(false);
      }
    },
    [organizationId, documentId, pendingTurnId, loading]
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
  };

  return {
    state,
    sendMessage,
    approveToolCalls,
    setAutoApprove,
    setModel,
    setError,
    loadModels,
  };
}
