import type { ComponentType } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import CasesPage from '@/pages/orgs/cases';
import CaseDetailPage from '@/pages/orgs/case-detail';
import CaseEditPage from '@/pages/orgs/case-edit';
import TagsPage from '@/pages/orgs/tags';
import TagEditPage from '@/pages/orgs/tag-edit';
import SchemasPage from '@/pages/orgs/schemas';
import SchemaEditPage from '@/pages/orgs/schema-edit';
import SchemaByIdRedirectPage from '@/pages/orgs/schema-by-id-redirect';
import PromptsPage from '@/pages/orgs/prompts';
import PromptEditPage from '@/pages/orgs/prompt-edit';
import PromptByIdRedirectPage from '@/pages/orgs/prompt-by-id-redirect';
import FormsPage from '@/pages/orgs/forms';
import FormEditPage from '@/pages/orgs/form-edit';
import FormByIdRedirectPage from '@/pages/orgs/form-by-id-redirect';
import KnowledgeBasesPage from '@/pages/orgs/knowledge-bases';
import ModelsPage from '@/pages/orgs/models';
import UploadPageClient from '@/pages/orgs/upload-client';
import FlowsPageClient, { type FlowsTab } from '@/pages/orgs/flows-client';
import FlowDetailPageClient from '@/pages/orgs/flow-detail-client';

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
