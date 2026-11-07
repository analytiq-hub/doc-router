import type { ComponentType } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import CasesPage from '@/app/orgs/[organizationId]/cases/page';
import CaseDetailPage from '@/app/orgs/[organizationId]/cases/[caseId]/page';
import CaseEditPage from '@/app/orgs/[organizationId]/cases/[caseId]/edit/page';
import TagsPage from '@/app/orgs/[organizationId]/tags/page';
import TagEditPage from '@/app/orgs/[organizationId]/tags/[tagId]/page';
import SchemasPage from '@/app/orgs/[organizationId]/schemas/page';
import SchemaEditPage from '@/app/orgs/[organizationId]/schemas/[schemaRevId]/page';
import SchemaByIdRedirectPage from '@/app/orgs/[organizationId]/schemas/by-id/[schemaId]/page';
import PromptsPage from '@/app/orgs/[organizationId]/prompts/page';
import PromptEditPage from '@/app/orgs/[organizationId]/prompts/[promptRevId]/page';
import PromptByIdRedirectPage from '@/app/orgs/[organizationId]/prompts/by-id/[promptId]/page';
import FormsPage from '@/app/orgs/[organizationId]/forms/page';
import FormEditPage from '@/app/orgs/[organizationId]/forms/[formId]/page';
import FormByIdRedirectPage from '@/app/orgs/[organizationId]/forms/by-id/[formId]/page';
import KnowledgeBasesPage from '@/app/orgs/[organizationId]/knowledge-bases/page';
import ModelsPage from '@/app/orgs/[organizationId]/models/page';
import UploadPageClient from '@/app/orgs/[organizationId]/upload/UploadPageClient';
import FlowsPageClient, { type FlowsTab } from '@/app/orgs/[organizationId]/flows/FlowsPageClient';
import FlowDetailPageClient from '@/app/orgs/[organizationId]/flows/[flowId]/FlowDetailPageClient';

import { withRouteParams } from './withRouteParams';

function withOrgParams(Page: ComponentType<{ params: Promise<{ organizationId: string }> }>) {
  return withRouteParams(['organizationId'], Page);
}

export const OrgCases = withOrgParams(CasesPage);
export const OrgCaseDetail = withRouteParams(
  ['organizationId', 'caseId'],
  CaseDetailPage,
);
export const OrgCaseEdit = CaseEditPage;
export const OrgTags = withOrgParams(TagsPage);
export const OrgTagEdit = TagEditPage;
export const OrgSchemas = withOrgParams(SchemasPage);
export const OrgSchemaEdit = SchemaEditPage;
export const OrgSchemaByIdRedirect = withRouteParams(
  ['organizationId', 'schemaId'],
  SchemaByIdRedirectPage,
);
export const OrgPrompts = withOrgParams(PromptsPage);
export const OrgPromptEdit = PromptEditPage;
export const OrgPromptByIdRedirect = withRouteParams(
  ['organizationId', 'promptId'],
  PromptByIdRedirectPage,
);
export const OrgForms = withOrgParams(FormsPage);
export const OrgFormEdit = FormEditPage;
export const OrgFormByIdRedirect = withRouteParams(
  ['organizationId', 'formId'],
  FormByIdRedirectPage,
);
export const OrgKnowledgeBases = withOrgParams(KnowledgeBasesPage);
export const OrgModels = withOrgParams(ModelsPage);

export function OrgUpload() {
  const { organizationId } = useParams();
  if (!organizationId) return null;
  return <UploadPageClient organizationId={organizationId} />;
}

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
