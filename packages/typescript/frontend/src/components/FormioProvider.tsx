'use client';

import { useEffect } from 'react';
import { useAppSession } from '@/contexts/AppSessionContext';
import { publicFastApiFrontendUrl } from '@/config/publicEnv';

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
      const tailwindModule = await import("@tsed/tailwind-formio");
      const tailwind = tailwindModule.default ?? tailwindModule;

      // Initialize Formio with Tailwind (uses Boxicons by default)
      // eslint-disable-next-line react-hooks/rules-of-hooks -- Formio.use is not a React hook
      Formio.use(tailwind);
      Templates.framework = "tailwind";
    };

    window.FASTAPI_URL = publicFastApiFrontendUrl();

    initializeFormio();
  }, [session]);

  return <>{children}</>;
} 