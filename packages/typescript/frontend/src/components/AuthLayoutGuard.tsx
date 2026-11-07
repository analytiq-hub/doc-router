'use client';

import { useEffect } from 'react';
import { Navigate, useInRouterContext } from 'react-router-dom';

import { useAppSession } from '@/contexts/AppSessionContext';

function AuthSpinner() {
  return (
    <div className="flex min-h-[12rem] items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
    </div>
  );
}

function ClientRedirect({ to }: { to: string }) {
  const inRouter = useInRouterContext();
  useEffect(() => {
    if (!inRouter) window.location.assign(to);
  }, [inRouter, to]);
  if (inRouter) return <Navigate to={to} replace />;
  return null;
}

type AuthLayoutGuardProps = {
  children: React.ReactNode;
  requireSysAdmin?: boolean;
  /** Signed-out redirect (default `/`). */
  unauthenticatedTo?: string;
};

/**
 * Client auth gate for Next `layout.tsx` shells and standalone pages.
 * Works in the Vite SPA (React Router) and Next client layouts (full navigation).
 */
export function AuthLayoutGuard({
  children,
  requireSysAdmin = false,
  unauthenticatedTo = '/',
}: AuthLayoutGuardProps) {
  const { session, status } = useAppSession();

  if (status === 'loading') return <AuthSpinner />;
  if (!session) return <ClientRedirect to={unauthenticatedTo} />;
  if (requireSysAdmin && !session.user.isSysadmin) {
    return <ClientRedirect to="/settings" />;
  }
  return <>{children}</>;
}
