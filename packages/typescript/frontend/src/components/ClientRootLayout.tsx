'use client';

import React from 'react';

import FormioProvider from '@/components/FormioProvider';
import Layout from '@/components/Layout';
import ThemeRegistry from '@/components/ThemeRegistry';
import { AppSessionProvider } from '@/contexts/AppSessionContext';
import { OrganizationProvider } from '@/contexts/OrganizationContext';
import { Toaster } from 'react-hot-toast';
import { ToastContainer } from 'react-toastify';

/** Next.js root shell — session loads client-side (same as Vite `AppProviders`). */
export function ClientRootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeRegistry>
      <AppSessionProvider initialSession={null}>
        <OrganizationProvider>
          <FormioProvider>
            <Layout>{children}</Layout>
          </FormioProvider>
        </OrganizationProvider>
      </AppSessionProvider>
      <ToastContainer position="top-right" />
      <Toaster position="top-right" />
    </ThemeRegistry>
  );
}
