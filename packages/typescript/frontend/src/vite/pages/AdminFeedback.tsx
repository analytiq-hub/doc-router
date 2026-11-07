import { Navigate } from 'react-router-dom';

import Layout from '@/components/Layout';
import FeedbackAdmin from '@/components/FeedbackAdmin';
import { useAppSession } from '@/contexts/AppSessionContext';
import { isSysAdmin } from '@/utils/roles';

export function AdminFeedbackPage() {
  const { session, status } = useAppSession();

  if (status === 'loading') {
    return (
      <Layout>
        <div className="container mx-auto px-4 py-8 text-gray-600">Loading…</div>
      </Layout>
    );
  }

  if (!session || !isSysAdmin(session)) {
    return <Navigate to="/" replace />;
  }

  return (
    <Layout>
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">Feedback Review</h1>
        <FeedbackAdmin />
      </div>
    </Layout>
  );
}
