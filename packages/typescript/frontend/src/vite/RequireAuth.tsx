import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAppSession } from '@/contexts/AppSessionContext';

function AuthSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
    </div>
  );
}

/** Signed-in users only; otherwise send to sign-in with return URL. */
export function RequireAuth() {
  const { status } = useAppSession();
  const location = useLocation();

  if (status === 'loading') return <AuthSpinner />;
  if (status === 'unauthenticated') {
    const from = location.pathname + location.search;
    return <Navigate to={`/auth/signin?from=${encodeURIComponent(from)}`} replace />;
  }
  return <Outlet />;
}
