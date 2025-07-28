import "@/styles/globals.css";
import 'formiojs/dist/formio.full.min.css';
// import '@tsed/tailwind-formio/styles/index.css';
import '@/styles/formio/index.css';
import '@/styles/formio-custom.css';
import 'boxicons/css/boxicons.min.css';
import React from 'react';
import SessionProvider from "@/components/SessionProvider"
import Layout from '@/components/Layout';
import ThemeRegistry from '@/components/ThemeRegistry';
import { OrganizationProvider } from '@/contexts/OrganizationContext';
import { getAppServerSession } from '@/utils/session';
import { Toaster } from 'react-hot-toast';
import { ToastContainer } from 'react-toastify';
import FormioProvider from '@/components/FormioProvider';

export const metadata = {
  title: 'Smart Document Router - Forms',
  description: 'Smart Document Router Forms',
  icons: {
    icon: '/favicon.ico',
  },
};

export default async function FormioLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const appSession = await getAppServerSession();
  return (
    <html lang="en">
      <body>
        <ThemeRegistry>
          <SessionProvider session={appSession}>
            <OrganizationProvider>
              <FormioProvider>
                <Layout>{children}</Layout>
              </FormioProvider>
            </OrganizationProvider>
          </SessionProvider>
        </ThemeRegistry>
        <ToastContainer position="top-right" />
        <Toaster position="top-right" />
      </body>
    </html>
  );
} 