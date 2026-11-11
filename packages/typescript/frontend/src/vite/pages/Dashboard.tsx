import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDashboardRedirect } from '@/hooks/useDashboardRedirect';

export function DashboardPage() {
  const navigate = useNavigate();
  const go = useCallback((path: string) => navigate(path), [navigate]);
  useDashboardRedirect(go);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary-500" />
    </div>
  );
}
