import React, { useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { AppSessionProvider } from '@/contexts/AppSessionContext';
import { Toaster as SonnerToaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { createQueryClient } from '@/api/queryClient';
/** Session + theme only — router-bound providers live in `RouterProviders`. */
export function AppProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => createQueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <AppSessionProvider initialSession={null}>
          {children}
        </AppSessionProvider>
        <SonnerToaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
