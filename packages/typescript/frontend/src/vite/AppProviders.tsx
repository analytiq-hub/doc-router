import React from 'react';
import { AppSessionProvider } from '@/contexts/AppSessionContext';
import { Toaster as SonnerToaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ThemeShell } from './ThemeShell';
import { Toaster } from 'react-hot-toast';
import { ToastContainer } from 'react-toastify';

/** Session + theme only — router-bound providers live in `RouterProviders`. */
export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeShell>
      <TooltipProvider>
        <AppSessionProvider initialSession={null}>
          {children}
        </AppSessionProvider>
        <SonnerToaster position="top-right" richColors closeButton />
        <ToastContainer position="top-right" />
        <Toaster position="top-right" />
      </TooltipProvider>
    </ThemeShell>
  );
}
