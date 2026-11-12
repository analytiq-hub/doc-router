import { useQuery, useQueryClient } from '@tanstack/react-query'

import { DocRouterOrgApi } from '@/utils/api'

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

export function useInvalidateOrgLists(organizationId: string) {
  const client = useQueryClient()
  return {
    prompts: () => client.invalidateQueries({ queryKey: orgKeys.prompts(organizationId) }),
    forms: () => client.invalidateQueries({ queryKey: orgKeys.forms(organizationId) }),
    schemas: () => client.invalidateQueries({ queryKey: orgKeys.schemas(organizationId) }),
    tags: () => client.invalidateQueries({ queryKey: orgKeys.tags(organizationId) }),
  }
}
