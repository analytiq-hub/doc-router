import { useCallback, useMemo } from 'react';
import { useQueries, useQueryClient } from '@tanstack/react-query';
import type { GetLLMResultResponse } from '@docrouter/sdk';

import { DocRouterOrgApi } from '@/utils/api';

export const promptResultKey = (
  organizationId: string,
  documentId: string,
  promptRevId: string,
) => ['org', organizationId, 'documents', documentId, 'llm-result', promptRevId] as const;

function statusFromError(error: unknown): number | undefined {
  if (!error || typeof error !== 'object') return undefined;
  const candidate = error as { status?: unknown; response?: { status?: unknown } };
  const raw = candidate.status ?? candidate.response?.status;
  if (typeof raw === 'number') return raw;
  if (typeof raw === 'string') {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function isNotFound(error: unknown): boolean {
  const message = error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase();
  return statusFromError(error) === 404 || message.includes('not found');
}

type PromptResultEntry = {
  data?: GetLLMResultResponse | null;
  pending: boolean;
  failed: boolean;
};

/**
 * One shared query per document/prompt revision. Loading the collapsed preview and expanding a row
 * use the same request, so React strict-mode remounts and quick clicks cannot create competing
 * fetches or leave hand-maintained "prefetching" flags behind.
 */
export function usePromptResults({
  organizationId,
  documentId,
  promptRevIds,
  enabled,
}: {
  organizationId: string;
  documentId: string;
  promptRevIds: string[];
  enabled: boolean;
}) {
  const queryClient = useQueryClient();
  const api = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const ids = useMemo(() => [...new Set(promptRevIds)], [promptRevIds]);
  const queries = useQueries({
    queries: ids.map((promptRevId) => ({
      queryKey: promptResultKey(organizationId, documentId, promptRevId),
      queryFn: async (): Promise<GetLLMResultResponse | null> => {
        try {
          return await api.getLLMResult({
            documentId,
            promptRevId,
            promptRevIdFallback: promptRevId !== 'default',
          });
        } catch (error) {
          if (isNotFound(error)) return null;
          throw error;
        }
      },
      enabled,
      staleTime: 30_000,
      retry: (failureCount: number, error: unknown) => !isNotFound(error) && failureCount < 1,
    })),
  });

  const byPrompt = useMemo(() => {
    const map: Record<string, PromptResultEntry> = {};
    ids.forEach((id, index) => {
      const query = queries[index];
      map[id] = {
        data: query.data,
        pending: enabled && query.isPending && query.fetchStatus === 'fetching',
        failed: query.isError,
      };
    });
    return map;
  }, [enabled, ids, queries]);

  const results = useMemo(() => {
    const map: Record<string, GetLLMResultResponse> = {};
    for (const [id, entry] of Object.entries(byPrompt)) {
      if (entry.data) map[id] = entry.data;
    }
    return map;
  }, [byPrompt]);

  const setResult = useCallback(
    (promptRevId: string, result: GetLLMResultResponse | null) => {
      queryClient.setQueryData(
        promptResultKey(organizationId, documentId, promptRevId),
        result,
      );
    },
    [documentId, organizationId, queryClient],
  );

  const fetchResult = useCallback(
    (promptRevId: string, fallback = promptRevId !== 'default') =>
      queryClient.fetchQuery({
        queryKey: promptResultKey(organizationId, documentId, promptRevId),
        queryFn: async () => {
          try {
            return await api.getLLMResult({
              documentId,
              promptRevId,
              promptRevIdFallback: fallback,
            });
          } catch (error) {
            if (isNotFound(error)) return null;
            throw error;
          }
        },
        staleTime: 0,
      }),
    [api, documentId, organizationId, queryClient],
  );

  return { byPrompt, results, setResult, fetchResult };
}
