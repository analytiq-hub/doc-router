'use client';

import { useEffect } from 'react';

export default function FormioProvider({
  children
}: {
  children: React.ReactNode
}) {
  useEffect(() => {
    // Only initialize Formio on the client side
    const initializeFormio = async () => {
      const { Formio, Templates } = await import("@tsed/react-formio");
      const tailwind = await import("@/vendor/tailwind-formio");
      
      // Initialize Formio with Tailwind (uses Boxicons by default)
      Formio.use(tailwind.default);
      Templates.framework = "tailwind";
    };

    initializeFormio();
  }, []);

  return <>{children}</>;
} 