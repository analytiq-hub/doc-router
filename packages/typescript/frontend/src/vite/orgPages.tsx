import type { ComponentType } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import CasesPage from '@/app/orgs/[organizationId]/cases/page';
import TagsPage from '@/app/orgs/[organizationId]/tags/page';
import SchemasPage from '@/app/orgs/[organizationId]/schemas/page';
import PromptsPage from '@/app/orgs/[organizationId]/prompts/page';
import FormsPage from '@/app/orgs/[organizationId]/forms/page';
import KnowledgeBasesPage from '@/app/orgs/[organizationId]/knowledge-bases/page';
import FlowsPageClient, { type FlowsTab } from '@/app/orgs/[organizationId]/flows/FlowsPageClient';
import FlowDetailPageClient from '@/app/orgs/[organizationId]/flows/[flowId]/FlowDetailPageClient';

function withOrgParams(Page: ComponentType<{ params: Promise<{ organizationId: string }> }>) {
  function Wrapped() {
    const { organizationId } = useParams();
    if (!organizationId) return null;
    return <Page params={Promise.resolve({ organizationId })} />;
  }
  return Wrapped;
}

export const OrgCases = withOrgParams(CasesPage);
export const OrgTags = withOrgParams(TagsPage);
export const OrgSchemas = withOrgParams(SchemasPage);
export const OrgPrompts = withOrgParams(PromptsPage);
export const OrgForms = withOrgParams(FormsPage);
export const OrgKnowledgeBases = withOrgParams(KnowledgeBasesPage);

export function OrgFlows() {
  const { organizationId } = useParams();
  const [searchParams] = useSearchParams();
  if (!organizationId) return null;

  const rawTab = searchParams.get('tab') || 'flows';
  const tab: FlowsTab =
    rawTab === 'credentials' || rawTab === 'executions' ? rawTab : 'flows';
  const newFlow = searchParams.get('newFlow') === '1';
  const autoCreateCredential =
    searchParams.get('newCredential') === '1' || searchParams.get('bootstrapCredential') === '1';

  return (
    <FlowsPageClient
      organizationId={organizationId}
      tab={tab}
      newFlow={newFlow}
      autoCreateCredential={autoCreateCredential}
    />
  );
}

export function OrgFlowDetail() {
  const { organizationId, flowId } = useParams();
  if (!organizationId || !flowId) return null;
  return (
    <FlowDetailPageClient
      key={`${organizationId}:${flowId}`}
      organizationId={organizationId}
      flowId={flowId}
    />
  );
}
