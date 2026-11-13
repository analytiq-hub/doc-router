/** @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getLLMResult = vi.fn();

vi.mock('@/utils/api', () => ({
  DocRouterOrgApi: class {
    getLLMResult = getLLMResult;
  },
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const resultFixture = {
  prompt_revid: 'prompt-v1',
  prompt_version: 1,
  updated_llm_result: { name: 'David Kim' },
};

describe('usePromptResults', () => {
  beforeEach(() => {
    getLLMResult.mockReset();
  });

  it('loads each prompt once and exposes cached results', async () => {
    getLLMResult.mockResolvedValue(resultFixture);
    const { usePromptResults } = await import('./usePromptResults');
    const { result, rerender } = renderHook(
      () =>
        usePromptResults({
          organizationId: 'org-1',
          documentId: 'doc-1',
          promptRevIds: ['prompt-v1', 'prompt-v1'],
          enabled: true,
        }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.results['prompt-v1']).toBeDefined());
    rerender();
    expect(getLLMResult).toHaveBeenCalledTimes(1);
  });

  it('deduplicates an explicit fetch while the row query is in flight', async () => {
    let resolve: (value: typeof resultFixture) => void = () => {};
    getLLMResult.mockReturnValue(new Promise((done) => (resolve = done)));
    const { usePromptResults } = await import('./usePromptResults');
    const { result } = renderHook(
      () =>
        usePromptResults({
          organizationId: 'org-1',
          documentId: 'doc-1',
          promptRevIds: ['prompt-v1'],
          enabled: true,
        }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.byPrompt['prompt-v1']?.pending).toBe(true));
    const expandedFetch = result.current.fetchResult('prompt-v1');
    expect(getLLMResult).toHaveBeenCalledTimes(1);
    resolve(resultFixture);
    await expect(expandedFetch).resolves.toEqual(resultFixture);
  });

  it('treats a missing result as an empty row rather than a failed request', async () => {
    getLLMResult.mockRejectedValue(Object.assign(new Error('not found'), { status: 404 }));
    const { usePromptResults } = await import('./usePromptResults');
    const { result } = renderHook(
      () =>
        usePromptResults({
          organizationId: 'org-1',
          documentId: 'doc-1',
          promptRevIds: ['prompt-v1'],
          enabled: true,
        }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.byPrompt['prompt-v1']?.data).toBeNull());
    expect(result.current.byPrompt['prompt-v1']?.failed).toBe(false);
  });
});
