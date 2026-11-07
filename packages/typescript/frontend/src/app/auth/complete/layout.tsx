import { Suspense, type ReactNode } from 'react';

/** Next.js only — Vite uses `vite/pages/AuthComplete`. */
export default function AuthCompleteLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<div className="mt-8 flex justify-center text-gray-600">Completing sign-in…</div>}>
      {children}
    </Suspense>
  );
}
