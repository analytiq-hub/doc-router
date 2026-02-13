import "@/styles/globals.css";
import React from 'react';
import SessionProvider from "@/components/SessionProvider"
import Layout from '@/components/Layout';
import ThemeRegistry from '@/components/ThemeRegistry';
import { OrganizationProvider } from '@/contexts/OrganizationContext';
import { AppSessionProvider } from '@/contexts/AppSessionContext';
import { getAppServerSession } from '@/utils/session';
import { Toaster } from 'react-hot-toast';
import { ToastContainer } from 'react-toastify';
import FormioProvider from '@/components/FormioProvider';

export const metadata = {
  title: 'Smart Document Router',
  description: 'Smart Document Router',
  icons: {
    icon: '/favicon.ico',
  },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const appSession = await getAppServerSession();
  return (
    <html lang="en">
      <head>
        <link rel="stylesheet" href="/formio.full.css" />
      </head>
      <body>
        <ThemeRegistry>
          <SessionProvider session={appSession}>
            <AppSessionProvider>
              <OrganizationProvider>
                <FormioProvider>
                  <Layout>{children}</Layout>
                </FormioProvider>
              </OrganizationProvider>
            </AppSessionProvider>
          </SessionProvider>
        </ThemeRegistry>
        <ToastContainer position="top-right" />
        <Toaster position="top-right" />
      </body>
    </html>
  );
}
