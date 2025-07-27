import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/auth';
import { redirect } from 'next/navigation';
import FeedbackAdmin from '@/components/FeedbackAdmin';

export const metadata = {
  title: 'Admin Feedback Review',
  description: 'Review user feedback submissions',
};

export default async function AdminFeedbackPage() {
  // Get session server-side
  const session = await getServerSession(authOptions);
  
  // Check if user is admin
  const isAdmin = session?.user?.role === 'admin';
  
  // Add more visible logging
  console.log('==== ADMIN FEEDBACK PAGE ====');
  console.log('Session:', JSON.stringify(session, null, 2));
  console.log('Is Admin:', isAdmin);
  console.log('==============================');

  // Redirect non-admin users
  if (!session || !isAdmin) {
    console.log('Redirecting non-admin user');
    redirect('/');
  }
  
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Feedback Review</h1>
      <FeedbackAdmin />
    </div>
  );
} 