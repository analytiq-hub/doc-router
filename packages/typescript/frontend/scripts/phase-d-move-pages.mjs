#!/usr/bin/env node
/**
 * Move app router page implementations to src/pages and leave Next stubs.
 * Run from packages/typescript/frontend.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = path.join(root, 'src');
const app = path.join(src, 'app');
const pages = path.join(src, 'pages');

/** @type {{ from: string; to: string }[]} */
const MOVES = [
  // settings
  { from: 'settings/page.tsx', to: 'settings/index.tsx' },
  { from: 'settings/organizations/page.tsx', to: 'settings/organizations.tsx' },
  { from: 'settings/organizations/[organizationId]/page.tsx', to: 'settings/organization-edit.tsx' },
  { from: 'settings/organizations/[organizationId]/webhooks/page.tsx', to: 'settings/organization-webhooks.tsx' },
  { from: 'settings/organizations/[organizationId]/subscription/page.tsx', to: 'settings/organization-subscription.tsx' },
  { from: 'settings/user/profile/page.tsx', to: 'settings/user-profile.tsx' },
  { from: 'settings/user/developer/page.tsx', to: 'settings/user-developer.tsx' },
  { from: 'settings/user/access-tokens/page.tsx', to: 'settings/user-access-tokens.tsx' },
  { from: 'settings/user/developer/account-access-tokens/page.tsx', to: 'settings/developer-account-tokens.tsx' },
  { from: 'settings/user/developer/organization-access-tokens/page.tsx', to: 'settings/developer-org-tokens.tsx' },
  { from: 'settings/user/developer/organization-webhooks/page.tsx', to: 'settings/developer-org-webhooks.tsx' },
  { from: 'settings/account/users/page.tsx', to: 'settings/account-users.tsx' },
  { from: 'settings/account/users/[userId]/page.tsx', to: 'settings/account-user-detail.tsx' },
  { from: 'settings/account/license/page.tsx', to: 'settings/account-license.tsx' },
  { from: 'settings/account/development/page.tsx', to: 'settings/account-development.tsx' },
  { from: 'settings/account/development/aws-config/page.tsx', to: 'settings/development-aws-config.tsx' },
  { from: 'settings/account/development/aws-credentials/page.tsx', to: 'settings/development-aws-credentials.tsx' },
  { from: 'settings/account/development/azure-config/page.tsx', to: 'settings/development-azure-config.tsx' },
  { from: 'settings/account/development/gcp-config/page.tsx', to: 'settings/development-gcp-config.tsx' },
  { from: 'settings/account/development/worker-settings/page.tsx', to: 'settings/development-worker-settings.tsx' },
  { from: 'settings/account/development/llm-manager/page.tsx', to: 'settings/development-llm-manager.tsx' },
  { from: 'settings/account/development/llm-manager/models/page.tsx', to: 'settings/development-llm-manager-models.tsx' },
  {
    from: 'settings/account/development/llm-manager/providers/[providerName]/page.tsx',
    to: 'settings/development-llm-provider.tsx',
  },
  // org list pages
  { from: 'orgs/[organizationId]/cases/page.tsx', to: 'orgs/cases.tsx' },
  { from: 'orgs/[organizationId]/cases/[caseId]/page.tsx', to: 'orgs/case-detail.tsx' },
  { from: 'orgs/[organizationId]/cases/[caseId]/edit/page.tsx', to: 'orgs/case-edit.tsx' },
  { from: 'orgs/[organizationId]/tags/page.tsx', to: 'orgs/tags.tsx' },
  { from: 'orgs/[organizationId]/tags/[tagId]/page.tsx', to: 'orgs/tag-edit.tsx' },
  { from: 'orgs/[organizationId]/schemas/page.tsx', to: 'orgs/schemas.tsx' },
  { from: 'orgs/[organizationId]/schemas/[schemaRevId]/page.tsx', to: 'orgs/schema-edit.tsx' },
  { from: 'orgs/[organizationId]/schemas/by-id/[schemaId]/page.tsx', to: 'orgs/schema-by-id-redirect.tsx' },
  { from: 'orgs/[organizationId]/prompts/page.tsx', to: 'orgs/prompts.tsx' },
  { from: 'orgs/[organizationId]/prompts/[promptRevId]/page.tsx', to: 'orgs/prompt-edit.tsx' },
  { from: 'orgs/[organizationId]/prompts/by-id/[promptId]/page.tsx', to: 'orgs/prompt-by-id-redirect.tsx' },
  { from: 'orgs/[organizationId]/forms/page.tsx', to: 'orgs/forms.tsx' },
  { from: 'orgs/[organizationId]/forms/[formId]/page.tsx', to: 'orgs/form-edit.tsx' },
  { from: 'orgs/[organizationId]/forms/by-id/[formId]/page.tsx', to: 'orgs/form-by-id-redirect.tsx' },
  { from: 'orgs/[organizationId]/knowledge-bases/page.tsx', to: 'orgs/knowledge-bases.tsx' },
  { from: 'orgs/[organizationId]/models/page.tsx', to: 'orgs/models.tsx' },
  { from: 'orgs/[organizationId]/dashboard/page.tsx', to: 'orgs/dashboard.tsx' },
  { from: 'orgs/[organizationId]/docs/page.tsx', to: 'orgs/documents.tsx' },
  { from: 'orgs/[organizationId]/docs/[id]/page.tsx', to: 'orgs/document-viewer.tsx' },
  // org clients (co-located)
  { from: 'orgs/[organizationId]/upload/UploadPageClient.tsx', to: 'orgs/upload-client.tsx' },
  { from: 'orgs/[organizationId]/docs/DocumentsPageClient.tsx', to: 'orgs/documents-client.tsx' },
  { from: 'orgs/[organizationId]/docs/[id]/PDFViewerClient.tsx', to: 'orgs/pdf-viewer-client.tsx' },
  { from: 'orgs/[organizationId]/flows/FlowsPageClient.tsx', to: 'orgs/flows-client.tsx' },
  { from: 'orgs/[organizationId]/flows/[flowId]/FlowDetailPageClient.tsx', to: 'orgs/flow-detail-client.tsx' },
  // misc app pages
  { from: 'dashboard/page.tsx', to: 'dashboard.tsx' },
  { from: 'system/page.tsx', to: 'system.tsx' },
  { from: 'feedback/page.tsx', to: 'feedback.tsx' },
  { from: 'admin/feedback/page.tsx', to: 'admin-feedback.tsx' },
];

function stubExport(importPath) {
  return `export { default } from '${importPath}';\n`;
}

for (const { from, to } of MOVES) {
  const fromAbs = path.join(app, from);
  const toAbs = path.join(pages, to);
  if (!fs.existsSync(fromAbs)) {
    console.warn('skip missing', from);
    continue;
  }
  fs.mkdirSync(path.dirname(toAbs), { recursive: true });
  fs.renameSync(fromAbs, toAbs);
  const importPath = `@/pages/${to.replace(/\.tsx$/, '')}`;
  if (from.endsWith('page.tsx')) {
    fs.writeFileSync(fromAbs, stubExport(importPath));
  }
  console.log('moved', from, '→', to);
}

// flows/upload Next wrappers referenced moved clients
const uploadStub = `'use client';

import UploadPageClient from '@/pages/orgs/upload-client';
import { useRouteParams } from '@/utils/useRouteParams';

export default function UploadPage(props: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = useRouteParams(props);
  return <UploadPageClient organizationId={organizationId} />;
}
`;
fs.writeFileSync(path.join(app, 'orgs/[organizationId]/upload/page.tsx'), uploadStub);

const flowsStub = `'use client';

import FlowsPageClient, { type FlowsTab } from '@/pages/orgs/flows-client';
import { useRouteParams } from '@/utils/useRouteParams';
import { useSearchParams } from '@/utils/appRouter';

export default function FlowsPage(props: { params: Promise<{ organizationId: string }> }) {
  const { organizationId } = useRouteParams(props);
  const searchParams = useSearchParams();
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
`;
fs.writeFileSync(path.join(app, 'orgs/[organizationId]/flows/page.tsx'), flowsStub);

const flowDetailStub = `'use client';

import FlowDetailPageClient from '@/pages/orgs/flow-detail-client';
import { useRouteParams } from '@/utils/useRouteParams';

export default function FlowDetailPage(props: {
  params: Promise<{ organizationId: string; flowId: string }>;
}) {
  const { organizationId, flowId } = useRouteParams(props);
  return (
    <FlowDetailPageClient
      key={\`\${organizationId}:\${flowId}\`}
      organizationId={organizationId}
      flowId={flowId}
    />
  );
}
`;
fs.writeFileSync(path.join(app, 'orgs/[organizationId]/flows/[flowId]/page.tsx'), flowDetailStub);

console.log('Phase D page move done');
