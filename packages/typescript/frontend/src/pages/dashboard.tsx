'use client'

import { useCallback } from 'react';
import { useRouter } from '@/utils/appRouter';
import { useDashboardRedirect } from '@/hooks/useDashboardRedirect';

export default function DashboardRedirect() {
  const router = useRouter();
  const navigate = useCallback((path: string) => router.push(path), [router]);
  useDashboardRedirect(navigate);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary-500"></div>
    </div>
  );
} 