import React, { useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { AppSessionProvider } from '@/contexts/AppSessionContext';
import { Toaster as SonnerToaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { createQueryClient } from '@/api/queryClient';
import { ThemeShell } from './ThemeShell';
import { Toaster } from 'react-hot-toast';
import { ToastContainer } from 'react-toastify';

/** Session + theme only — router-bound providers live in `RouterProviders`. */
export function AppProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => createQueryClient());
  return (
    <QueryClientProvider client={queryClient}>
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
    </QueryClientProvider>
  );
}
