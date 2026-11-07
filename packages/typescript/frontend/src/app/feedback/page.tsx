'use client';

import FeedbackForm from '@/components/FeedbackForm';
import { AuthLayoutGuard } from '@/components/AuthLayoutGuard';

export default function FeedbackPage() {
  return (
    <AuthLayoutGuard unauthenticatedTo={`/auth/signin?from=${encodeURIComponent('/feedback')}`}>
      <div className="container mx-auto px-4 py-8">
        <FeedbackForm />
      </div>
    </AuthLayoutGuard>
  );
}
