import { createBrowserRouter, Navigate, Outlet, type RouteObject } from 'react-router-dom';

import Layout from '@/components/Layout';
import { AuthCompletePage } from '@/vite/pages/AuthComplete';
import { DashboardPage } from '@/vite/pages/Dashboard';
import { HomePage } from '@/vite/pages/Home';
import { OrgPlaceholderPage } from '@/vite/pages/OrgPlaceholder';
import { SignInPage } from '@/vite/pages/SignIn';
import { OrgDashboard } from '@/vite/OrgDashboard';
import { OrgDocuments } from '@/vite/OrgDocuments';
import { OrgLayout } from '@/vite/OrgLayout';
import { RequireAuth } from '@/vite/RequireAuth';
import { RouterProviders } from '@/vite/RouterProviders';

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
              {
                path: 'orgs/:organizationId',
                element: <OrgLayout />,
                children: [
                  { index: true, element: <Navigate to="dashboard" replace /> },
                  { path: 'dashboard', element: <OrgDashboard /> },
                  { path: 'docs', element: <OrgDocuments /> },
                  { path: '*', element: <OrgPlaceholderPage /> },
                ],
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
