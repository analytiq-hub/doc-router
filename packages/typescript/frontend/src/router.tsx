import { createBrowserRouter, Navigate, Outlet, type RouteObject } from 'react-router-dom';

import Layout from '@/components/Layout';
import { lazyNamedRoute, lazyRoute } from '@/vite/lazyRoute';
import { RequireAuth } from '@/vite/RequireAuth';
import { RouterProviders } from '@/vite/RouterProviders';
import { OrgLayout } from '@/vite/OrgLayout';
import { SettingsAppLayout } from '@/vite/SettingsAppLayout';

const orgChildRoutes: RouteObject[] = [
  { index: true, element: <Navigate to="dashboard" replace /> },
  { path: 'dashboard', element: lazyNamedRoute(() => import('@/vite/OrgDashboard'), 'OrgDashboard') },
  { path: 'docs', element: lazyNamedRoute(() => import('@/vite/OrgDocuments'), 'OrgDocuments') },
  { path: 'docs/:id', element: lazyNamedRoute(() => import('@/vite/OrgDocumentViewer'), 'OrgDocumentViewer') },
  { path: 'upload', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgUpload') },
  { path: 'cases', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgCases') },
  { path: 'cases/:caseId', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgCaseDetail') },
  { path: 'cases/:caseId/edit', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgCaseEdit') },
  { path: 'tags', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgTags') },
  { path: 'tags/:tagId', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgTagEdit') },
  { path: 'schemas', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgSchemas') },
  { path: 'schemas/by-id/:schemaId', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgSchemaByIdRedirect') },
  { path: 'schemas/:schemaRevId', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgSchemaEdit') },
  { path: 'prompts', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgPrompts') },
  { path: 'prompts/by-id/:promptId', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgPromptByIdRedirect') },
  { path: 'prompts/:promptRevId', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgPromptEdit') },
  { path: 'forms', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgForms') },
  { path: 'forms/by-id/:formId', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgFormByIdRedirect') },
  { path: 'forms/:formId', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgFormEdit') },
  { path: 'knowledge-bases', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgKnowledgeBases') },
  { path: 'models', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgModels') },
  { path: 'flows', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgFlows') },
  { path: 'flows/:flowId', element: lazyNamedRoute(() => import('@/vite/orgPages'), 'OrgFlowDetail') },
  { path: '*', element: lazyNamedRoute(() => import('@/vite/pages/OrgPlaceholder'), 'OrgPlaceholderPage') },
];

const settingsChildRoutes: RouteObject[] = [
  { index: true, element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsIndex') },
  { path: 'organizations', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsOrganizations') },
  { path: 'organizations/:organizationId', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsOrganizationEdit') },
  { path: 'organizations/:organizationId/webhooks', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsOrganizationWebhooks') },
  { path: 'organizations/:organizationId/subscription', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsOrganizationSubscription') },
  { path: 'user/profile', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsUserProfile') },
  { path: 'user/developer', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsUserDeveloper') },
  { path: 'user/access-tokens', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsUserAccessTokens') },
  { path: 'user/developer/account-access-tokens', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsDeveloperAccountTokens') },
  { path: 'user/developer/organization-access-tokens', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsDeveloperOrgTokens') },
  { path: 'user/developer/organization-webhooks', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsDeveloperOrgWebhooks') },
  { path: 'account/users', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsAccountUsers') },
  { path: 'account/users/:userId', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsAccountUserDetail') },
  { path: 'account/license', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsAccountLicense') },
  { path: 'account/development', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsAccountDevelopment') },
  { path: 'account/development/aws-config', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsDevelopmentAwsConfig') },
  { path: 'account/development/aws-credentials', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsDevelopmentAwsCredentials') },
  { path: 'account/development/azure-config', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsDevelopmentAzureConfig') },
  { path: 'account/development/gcp-config', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsDevelopmentGcpConfig') },
  { path: 'account/development/worker-settings', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsDevelopmentWorkerSettings') },
  { path: 'account/development/llm-manager', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsDevelopmentLlmManager') },
  { path: 'account/development/llm-manager/models', element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsDevelopmentLlmManagerModels') },
  {
    path: 'account/development/llm-manager/providers/:providerName',
    element: lazyNamedRoute(() => import('@/vite/settingsPages'), 'SettingsDevelopmentLlmProvider'),
  },
];

export const routes: RouteObject[] = [
  {
    element: <RouterProviders />,
    children: [
      { path: '/auth/signin', element: lazyNamedRoute(() => import('@/vite/pages/SignIn'), 'SignInPage') },
      { path: '/auth/complete', element: lazyNamedRoute(() => import('@/vite/pages/AuthComplete'), 'AuthCompletePage') },
      { path: '/auth/accept-invitation', element: lazyRoute(() => import('@/pages/auth/accept-invitation')) },
      { path: '/auth/verify-email', element: lazyRoute(() => import('@/pages/auth/verify-email')) },
      { path: '/verify-email', element: lazyRoute(() => import('@/pages/verify-email')) },
      { path: '/oauth/flow-callback', element: lazyRoute(() => import('@/pages/oauth/flow-callback')) },
      {
        path: '/dev/ui-kit',
        element: lazyNamedRoute(() => import('@/vite/pages/UiKitDemo'), 'UiKitDemoPage'),
      },
      {
        path: '/',
        element: <Outlet />,
        children: [
          { index: true, element: lazyNamedRoute(() => import('@/vite/pages/Home'), 'HomePage') },
          { path: 'system', element: lazyNamedRoute(() => import('@/vite/pages/System'), 'SystemPage') },
          {
            element: <RequireAuth />,
            children: [
              { path: 'dashboard', element: lazyNamedRoute(() => import('@/vite/pages/Dashboard'), 'DashboardPage') },
              { path: 'feedback', element: lazyNamedRoute(() => import('@/vite/pages/Feedback'), 'FeedbackPage') },
              { path: 'admin/feedback', element: lazyNamedRoute(() => import('@/vite/pages/AdminFeedback'), 'AdminFeedbackPage') },
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
                      No route matches this path in the SPA.
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
