import { Link } from 'react-router-dom';
import Layout from '@/components/Layout';
import MarketingHome from '@/pages/home';
import { useAppSession } from '@/contexts/AppSessionContext';

export function HomePage() {
  const { session, status } = useAppSession();

  return (
    <Layout>
      <div className="relative">
        {status === 'authenticated' && (
          <div className="absolute top-4 right-4 z-10 flex gap-3 text-sm">
            <Link className="text-blue-600 hover:underline" to="/dashboard">
              Open dashboard
            </Link>
            {session?.user?.email && (
              <span className="text-gray-600 hidden sm:inline">{session.user.email}</span>
            )}
          </div>
        )}
        {status !== 'authenticated' && status !== 'loading' && (
          <div className="absolute top-4 right-4 z-10 text-sm">
            <Link className="text-blue-600 hover:underline" to="/auth/signin">
              Sign in
            </Link>
          </div>
        )}
        <MarketingHome />
      </div>
    </Layout>
  );
}
