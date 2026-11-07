import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { persistSessionToken } from '@/utils/backendAuth';
import { useAppSession } from '@/contexts/AppSessionContext';

/** Vite route — mirrors Next `auth/complete` for OAuth return and optional ?token=. */
export function AuthCompletePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refreshSession } = useAppSession();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = searchParams.get('token');
    const returnTo = searchParams.get('return_to') || '/dashboard';
    const dest = returnTo.startsWith('/') ? returnTo : '/';

    let cancelled = false;

    (async () => {
      try {
        if (token) {
          await persistSessionToken(token);
        }
        await refreshSession();
        if (!cancelled) {
          navigate(dest, { replace: true });
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
  }, [searchParams, navigate, refreshSession]);

  if (error) {
    return (
      <div className="flex flex-col items-center mt-8 px-4 text-red-600">{error}</div>
    );
  }

  return (
    <div className="flex flex-col items-center mt-8 px-4 text-gray-600">
      Completing sign-in…
    </div>
  );
}
