import React from 'react';
import FeedbackForm from '@/components/FeedbackForm';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/auth';
import { redirect } from 'next/navigation';

export const metadata = {
  title: 'Provide Feedback',
  description: 'Share your feedback, suggestions, or report issues',
};

export default async function FeedbackPage() {
  const session = await getServerSession(authOptions);
  
  if (!session) {
    redirect('/auth/signin?callbackUrl=/feedback');
  }
  
  return (
    <div className="container mx-auto px-4 py-8">
      <FeedbackForm />
    </div>
  );
}