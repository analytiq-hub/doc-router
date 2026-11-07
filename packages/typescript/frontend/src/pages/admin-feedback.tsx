'use client';

import FeedbackAdmin from '@/components/FeedbackAdmin';
import { AuthLayoutGuard } from '@/components/AuthLayoutGuard';

export default function AdminFeedbackPage() {
  return (
    <AuthLayoutGuard requireSysAdmin>
      <div className="container mx-auto px-4 py-8">
        <h1 className="mb-6 text-2xl font-bold">Feedback Review</h1>
        <FeedbackAdmin />
      </div>
    </AuthLayoutGuard>
  );
}
