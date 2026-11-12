import { useQuery, useQueryClient, type UseQueryOptions } from '@tanstack/react-query'

import type { ListKnowledgeBasesResponse } from '@docrouter/sdk'

import { DocRouterOrgApi } from '@/utils/api'
import { fetchAllOrgTags } from '@/utils/fetchAllOrgTags'

export const orgKeys = {
  tags: (organizationId: string) => ['org', organizationId, 'tags'] as const,
  tagList: (organizationId: string, params: object) =>
    [...orgKeys.tags(organizationId), 'list', params] as const,
  prompts: (organizationId: string) => ['org', organizationId, 'prompts'] as const,
  promptList: (organizationId: string, params: object) =>
    [...orgKeys.prompts(organizationId), 'list', params] as const,
  forms: (organizationId: string) => ['org', organizationId, 'forms'] as const,
  formList: (organizationId: string, params: object) =>
    [...orgKeys.forms(organizationId), 'list', params] as const,
  schemas: (organizationId: string) => ['org', organizationId, 'schemas'] as const,
  schemaList: (organizationId: string, params: object) =>
    [...orgKeys.schemas(organizationId), 'list', params] as const,
  cases: (organizationId: string) => ['org', organizationId, 'cases'] as const,
  caseList: (organizationId: string, params: object) =>
    [...orgKeys.cases(organizationId), 'list', params] as const,
  knowledgeBases: (organizationId: string) => ['org', organizationId, 'knowledge-bases'] as const,
  knowledgeBaseList: (organizationId: string, params: object) =>
    [...orgKeys.knowledgeBases(organizationId), 'list', params] as const,
  documents: (organizationId: string) => ['org', organizationId, 'documents'] as const,
  documentList: (organizationId: string, params: object) =>
    [...orgKeys.documents(organizationId), 'list', params] as const,
}

export type OrgPromptListParams = {
  skip: number
  limit: number
  nameSearch?: string
  sort?: string
  filters?: string
}

export type OrgFormListParams = {
  skip: number
  limit: number
  name_search?: string
  sort?: string
  filters?: string
}

export type OrgSchemaListParams = {
  skip: number
  limit: number
  nameSearch?: string
  sort?: string
  filters?: string
}

export type OrgTagListParams = {
  skip: number
  limit: number
  nameSearch?: string
  sort?: string
  filters?: string
}

export type OrgCaseListParams = {
  skip: number
  limit: number
  caseIdSearch?: string
  tagIds?: string
  metadataSearch?: string
  sort?: string
  filters?: string
}

export type OrgKnowledgeBaseListParams = {
  skip: number
  limit: number
  name_search?: string
  sort?: string
  filters?: string
}

export type OrgDocumentListParams = {
  skip: number
  limit: number
  nameSearch?: string
  tagIds?: string
  metadataSearch?: string
  caseId?: string
  sort?: string
  filters?: string
}

const orgApi = (organizationId: string) => new DocRouterOrgApi(organizationId)

export function useOrgPrompts(organizationId: string, params: OrgPromptListParams) {
  return useQuery({
    queryKey: orgKeys.promptList(organizationId, params),
    queryFn: () => orgApi(organizationId).listPrompts(params),
    placeholderData: (previous) => previous,
  })
}

export function useOrgForms(organizationId: string, params: OrgFormListParams) {
  return useQuery({
    queryKey: orgKeys.formList(organizationId, params),
    queryFn: () => orgApi(organizationId).listForms(params),
    placeholderData: (previous) => previous,
  })
}

export function useOrgSchemas(organizationId: string, params: OrgSchemaListParams) {
  return useQuery({
    queryKey: orgKeys.schemaList(organizationId, params),
    queryFn: () => orgApi(organizationId).listSchemas(params),
    placeholderData: (previous) => previous,
  })
}

export function useOrgTags(organizationId: string, params: OrgTagListParams, enabled = true) {
  return useQuery({
    queryKey: orgKeys.tagList(organizationId, params),
    queryFn: () => orgApi(organizationId).listTags(params),
    placeholderData: (previous) => previous,
    enabled,
  })
}

/** All org tags (paginated client-side; API max limit is 100). */
export function useOrgAllTags(organizationId: string, enabled = true) {
  return useQuery({
    queryKey: [...orgKeys.tags(organizationId), 'all'] as const,
    queryFn: () => fetchAllOrgTags(orgApi(organizationId)),
    enabled,
  })
}

export function useOrgCases(organizationId: string, params: OrgCaseListParams) {
  return useQuery({
    queryKey: orgKeys.caseList(organizationId, params),
    queryFn: () => orgApi(organizationId).listCases(params),
    placeholderData: (previous) => previous,
  })
}

export function useOrgKnowledgeBases(
  organizationId: string,
  params: OrgKnowledgeBaseListParams,
  options?: Pick<UseQueryOptions<ListKnowledgeBasesResponse>, 'refetchInterval' | 'refetchOnWindowFocus'>,
) {
  return useQuery({
    queryKey: orgKeys.knowledgeBaseList(organizationId, params),
    queryFn: () => orgApi(organizationId).listKnowledgeBases(params),
    placeholderData: (previous) => previous,
    ...options,
  })
}

export function useOrgDocuments(organizationId: string, params: OrgDocumentListParams) {
  return useQuery({
    queryKey: orgKeys.documentList(organizationId, params),
    queryFn: () => orgApi(organizationId).listDocuments(params),
    placeholderData: (previous) => previous,
  })
}

export type OrgKBDocumentsParams = {
  skip: number
  limit: number
}

export function useOrgKBDocuments(organizationId: string, kbId: string, params: OrgKBDocumentsParams) {
  return useQuery({
    queryKey: [...orgKeys.knowledgeBases(organizationId), kbId, 'documents', params] as const,
    queryFn: () => orgApi(organizationId).listKBDocuments({ kbId, skip: params.skip, limit: params.limit }),
    placeholderData: (previous) => previous,
    enabled: Boolean(kbId),
  })
}

export function useInvalidateOrgLists(organizationId: string) {
  const client = useQueryClient()
  return {
    prompts: () => client.invalidateQueries({ queryKey: orgKeys.prompts(organizationId) }),
    forms: () => client.invalidateQueries({ queryKey: orgKeys.forms(organizationId) }),
    schemas: () => client.invalidateQueries({ queryKey: orgKeys.schemas(organizationId) }),
    tags: () => client.invalidateQueries({ queryKey: orgKeys.tags(organizationId) }),
    cases: () => client.invalidateQueries({ queryKey: orgKeys.cases(organizationId) }),
    knowledgeBases: () => client.invalidateQueries({ queryKey: orgKeys.knowledgeBases(organizationId) }),
    documents: () => client.invalidateQueries({ queryKey: orgKeys.documents(organizationId) }),
  }
}
