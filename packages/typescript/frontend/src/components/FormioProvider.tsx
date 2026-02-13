'use client';

import { useEffect } from 'react';
import { useAppSession } from '@/contexts/AppSessionContext';

// Global type declarations for the proxy helper
declare global {
  interface Window {
    FASTAPI_URL: string;
    proxyFetch: (url: string, options?: RequestInit) => Promise<Response>;
    getLLMResult: (params: {
      organizationId: string;
      documentId: string;
      promptId: string;
    }) => Promise<unknown>;
  }
}

export default function FormioProvider({
  children
}: {
  children: React.ReactNode
}) {
  const { session } = useAppSession();
  useEffect(() => {
    // Only initialize Formio on the client side
    const initializeFormio = async () => {
      const { Formio, Templates } = await import("@tsed/react-formio");
      const tailwindModule = await import("@/lib/tailwind-formio-loader.cjs");
      const tailwind = tailwindModule.default ?? tailwindModule;

      // Initialize Formio with Tailwind (uses Boxicons by default)
      // eslint-disable-next-line react-hooks/rules-of-hooks -- Formio.use is not a React hook
      Formio.use(tailwind);
      Templates.framework = "tailwind";
    };

    // Initialize global helpers for FormIO calculated values
    const initializeGlobalHelpers = () => {
      // Make FASTAPI URL available globally for FormIO
      // for example:
      // window.FASTAPI_URL = process.env.NEXT_PUBLIC_FASTAPI_FRONTEND_URL || "http://localhost:8000";
    };

    initializeFormio();
    initializeGlobalHelpers();
  }, [session]);

  return <>{children}</>;
} 