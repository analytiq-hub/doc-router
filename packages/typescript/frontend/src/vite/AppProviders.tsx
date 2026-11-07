import React from 'react';
import { AppSessionProvider } from '@/contexts/AppSessionContext';
import { ThemeShell } from './ThemeShell';
import { Toaster } from 'react-hot-toast';
import { ToastContainer } from 'react-toastify';

/** Session + theme only — router-bound providers live in `RouterProviders`. */
export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeShell>
      <AppSessionProvider initialSession={null}>
        {children}
      </AppSessionProvider>
      <ToastContainer position="top-right" />
      <Toaster position="top-right" />
    </ThemeShell>
  );
}
