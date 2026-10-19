import React, { Suspense } from 'react';

export default function AuthCompleteLayout({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<div className="flex justify-center mt-8 text-gray-600">Completing sign-in…</div>}>{children}</Suspense>;
}
