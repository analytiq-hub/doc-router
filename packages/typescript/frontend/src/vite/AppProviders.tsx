import React from 'react';
import { AppSessionProvider } from '@/contexts/AppSessionContext';
import { OrganizationProvider } from '@/contexts/OrganizationContext';
import FormioProvider from '@/components/FormioProvider';
import { ThemeShell } from './ThemeShell';
import { Toaster } from 'react-hot-toast';
import { ToastContainer } from 'react-toastify';

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeShell>
      <AppSessionProvider initialSession={null}>
        <OrganizationProvider>
          <FormioProvider>
            {children}
          </FormioProvider>
        </OrganizationProvider>
      </AppSessionProvider>
      <ToastContainer position="top-right" />
      <Toaster position="top-right" />
    </ThemeShell>
  );
}
