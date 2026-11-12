import { Link, Navigate } from 'react-router-dom';
import Layout from '@/components/Layout';
import MarketingHome from '@/pages/home';
import { useAppSession } from '@/contexts/AppSessionContext';
import { RouteLoadingFallback } from '@/vite/lazyRoute';

export function HomePage() {
  const { status } = useAppSession();

  if (status === 'loading') {
    return (
      <Layout>
        <RouteLoadingFallback />
      </Layout>
    );
  }

  if (status === 'authenticated') {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <Layout>
      <div className="relative">
        <div className="absolute top-4 right-4 z-10 text-sm">
          <Link className="text-primary hover:underline" to="/auth/signin">
            Sign in
          </Link>
        </div>
        <MarketingHome />
      </div>
    </Layout>
  );
}
