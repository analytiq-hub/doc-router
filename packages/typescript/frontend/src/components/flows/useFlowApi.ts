import { useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';

export function useFlowApi(organizationId: string): DocRouterOrgApi {
  return useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
}

