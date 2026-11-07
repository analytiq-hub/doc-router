import { createBrowserRouter, Navigate, Outlet, type RouteObject } from 'react-router-dom';

import Layout from '@/components/Layout';
import { AdminFeedbackPage } from '@/vite/pages/AdminFeedback';
import { AuthCompletePage } from '@/vite/pages/AuthComplete';
import { DashboardPage } from '@/vite/pages/Dashboard';
import { FeedbackPage } from '@/vite/pages/Feedback';
import { HomePage } from '@/vite/pages/Home';
import { OrgPlaceholderPage } from '@/vite/pages/OrgPlaceholder';
import { SignInPage } from '@/vite/pages/SignIn';
import { OrgDashboard } from '@/vite/OrgDashboard';
import { OrgDocumentViewer } from '@/vite/OrgDocumentViewer';
import { OrgDocuments } from '@/vite/OrgDocuments';
import { OrgLayout } from '@/vite/OrgLayout';
import {
  OrgCaseDetail,
  OrgCaseEdit,
  OrgCases,
  OrgFlowDetail,
  OrgFlows,
  OrgFormByIdRedirect,
  OrgFormEdit,
  OrgForms,
  OrgKnowledgeBases,
  OrgModels,
  OrgPromptByIdRedirect,
  OrgPromptEdit,
  OrgPrompts,
  OrgSchemaByIdRedirect,
  OrgSchemaEdit,
  OrgSchemas,
  OrgTagEdit,
  OrgTags,
  OrgUpload,
} from '@/vite/orgPages';
import {
  SettingsAccountDevelopment,
  SettingsDevelopmentAwsConfig,
  SettingsDevelopmentAwsCredentials,
  SettingsDevelopmentAzureConfig,
  SettingsDevelopmentGcpConfig,
  SettingsDevelopmentLlmManager,
  SettingsDevelopmentLlmManagerModels,
  SettingsDevelopmentLlmProvider,
  SettingsDevelopmentWorkerSettings,
  SettingsAccountLicense,
  SettingsAccountUserDetail,
  SettingsAccountUsers,
  SettingsDeveloperAccountTokens,
  SettingsDeveloperOrgTokens,
  SettingsDeveloperOrgWebhooks,
  SettingsIndex,
  SettingsOrganizationEdit,
  SettingsOrganizations,
  SettingsOrganizationSubscription,
  SettingsOrganizationWebhooks,
  SettingsUserAccessTokens,
  SettingsUserDeveloper,
  SettingsUserProfile,
} from '@/vite/settingsPages';
import { RequireAuth } from '@/vite/RequireAuth';
import { RouterProviders } from '@/vite/RouterProviders';
import { SettingsAppLayout } from '@/vite/SettingsAppLayout';

const orgChildRoutes: RouteObject[] = [
  { index: true, element: <Navigate to="dashboard" replace /> },
  { path: 'dashboard', element: <OrgDashboard /> },
  { path: 'docs', element: <OrgDocuments /> },
  { path: 'docs/:id', element: <OrgDocumentViewer /> },
  { path: 'upload', element: <OrgUpload /> },
  { path: 'cases', element: <OrgCases /> },
  { path: 'cases/:caseId', element: <OrgCaseDetail /> },
  { path: 'cases/:caseId/edit', element: <OrgCaseEdit /> },
  { path: 'tags', element: <OrgTags /> },
  { path: 'tags/:tagId', element: <OrgTagEdit /> },
  { path: 'schemas', element: <OrgSchemas /> },
  { path: 'schemas/by-id/:schemaId', element: <OrgSchemaByIdRedirect /> },
  { path: 'schemas/:schemaRevId', element: <OrgSchemaEdit /> },
  { path: 'prompts', element: <OrgPrompts /> },
  { path: 'prompts/by-id/:promptId', element: <OrgPromptByIdRedirect /> },
  { path: 'prompts/:promptRevId', element: <OrgPromptEdit /> },
  { path: 'forms', element: <OrgForms /> },
  { path: 'forms/by-id/:formId', element: <OrgFormByIdRedirect /> },
  { path: 'forms/:formId', element: <OrgFormEdit /> },
  { path: 'knowledge-bases', element: <OrgKnowledgeBases /> },
  { path: 'models', element: <OrgModels /> },
  { path: 'flows', element: <OrgFlows /> },
  { path: 'flows/:flowId', element: <OrgFlowDetail /> },
  { path: '*', element: <OrgPlaceholderPage /> },
];

const settingsChildRoutes: RouteObject[] = [
  { index: true, element: <SettingsIndex /> },
  { path: 'organizations', element: <SettingsOrganizations /> },
  { path: 'organizations/:organizationId', element: <SettingsOrganizationEdit /> },
  { path: 'organizations/:organizationId/webhooks', element: <SettingsOrganizationWebhooks /> },
  { path: 'organizations/:organizationId/subscription', element: <SettingsOrganizationSubscription /> },
  { path: 'user/profile', element: <SettingsUserProfile /> },
  { path: 'user/developer', element: <SettingsUserDeveloper /> },
  { path: 'user/access-tokens', element: <SettingsUserAccessTokens /> },
  { path: 'user/developer/account-access-tokens', element: <SettingsDeveloperAccountTokens /> },
  { path: 'user/developer/organization-access-tokens', element: <SettingsDeveloperOrgTokens /> },
  { path: 'user/developer/organization-webhooks', element: <SettingsDeveloperOrgWebhooks /> },
  { path: 'account/users', element: <SettingsAccountUsers /> },
  { path: 'account/users/:userId', element: <SettingsAccountUserDetail /> },
  { path: 'account/license', element: <SettingsAccountLicense /> },
  { path: 'account/development', element: <SettingsAccountDevelopment /> },
  { path: 'account/development/aws-config', element: <SettingsDevelopmentAwsConfig /> },
  { path: 'account/development/aws-credentials', element: <SettingsDevelopmentAwsCredentials /> },
  { path: 'account/development/azure-config', element: <SettingsDevelopmentAzureConfig /> },
  { path: 'account/development/gcp-config', element: <SettingsDevelopmentGcpConfig /> },
  { path: 'account/development/worker-settings', element: <SettingsDevelopmentWorkerSettings /> },
  { path: 'account/development/llm-manager', element: <SettingsDevelopmentLlmManager /> },
  { path: 'account/development/llm-manager/models', element: <SettingsDevelopmentLlmManagerModels /> },
  {
    path: 'account/development/llm-manager/providers/:providerName',
    element: <SettingsDevelopmentLlmProvider />,
  },
];

export const routes: RouteObject[] = [
  {
    element: <RouterProviders />,
    children: [
      { path: '/auth/signin', element: <SignInPage /> },
      { path: '/auth/complete', element: <AuthCompletePage /> },
      {
        path: '/',
        element: <Outlet />,
        children: [
          { index: true, element: <HomePage /> },
          {
            element: <RequireAuth />,
            children: [
              { path: 'dashboard', element: <DashboardPage /> },
              { path: 'feedback', element: <FeedbackPage /> },
              { path: 'admin/feedback', element: <AdminFeedbackPage /> },
              {
                path: 'orgs/:organizationId',
                element: <OrgLayout />,
                children: orgChildRoutes,
              },
              {
                path: 'settings',
                element: <SettingsAppLayout />,
                children: settingsChildRoutes,
              },
              {
                path: '*',
                element: (
                  <Layout>
                    <main className="mx-auto max-w-lg p-6 text-sm text-gray-600">
                      This page is not in the Vite app yet. Open it on Next.js at port 3000.
                    </main>
                  </Layout>
                ),
              },
            ],
          },
        ],
      },
    ],
  },
];

export const router = createBrowserRouter(routes);
