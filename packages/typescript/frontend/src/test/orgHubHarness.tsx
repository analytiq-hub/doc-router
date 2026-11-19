import type { ReactElement, ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import {
  hubCase,
  hubDocument,
  hubForm,
  hubKnowledgeBase,
  hubPrompt,
  hubSchema,
  hubTag,
  ORG_HUB_ID,
} from '@/test/fixtures/orgHubRows'

export function listQueryResult<T>(data: T) {
  return {
    data,
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
    isPending: false,
    status: 'success' as const,
  }
}

export const orgHubQueryData = {
  tags: { tags: [hubTag], total_count: 1 },
  allTags: [hubTag],
  documents: { documents: [hubDocument], total_count: 1 },
  cases: { cases: [hubCase], total_count: 1 },
  schemas: { schemas: [hubSchema], total_count: 1 },
  prompts: { prompts: [hubPrompt], total_count: 1 },
  forms: { forms: [hubForm], total_count: 1 },
  knowledgeBases: { knowledge_bases: [hubKnowledgeBase], total_count: 1 },
}

export { ORG_HUB_ID }

function Providers({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

export function renderOrgHub(ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) {
  return render(ui, { wrapper: Providers, ...options })
}