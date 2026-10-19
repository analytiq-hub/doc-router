'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { persistSessionToken } from '@/utils/backendAuth';
import { useAppSession } from '@/contexts/AppSessionContext';

export default function AuthCompletePage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { refreshSession } = useAppSession();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = searchParams.get('token');
    const returnTo = searchParams.get('return_to') || '/dashboard';

    if (!token) {
      setError('Missing sign-in token');
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        await persistSessionToken(token);
        await refreshSession();
        if (!cancelled) {
          router.replace(returnTo.startsWith('/') ? returnTo : '/dashboard');
          router.refresh();
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Sign-in failed');
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [searchParams, router, refreshSession]);

  if (error) {
    return (
      <div className="flex flex-col items-center mt-8 px-4 text-red-600">
        {error}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center mt-8 px-4 text-gray-600">
      Completing sign-in…
    </div>
  );
}
