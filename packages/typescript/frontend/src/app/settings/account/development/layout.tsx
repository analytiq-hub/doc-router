import { redirect } from 'next/navigation';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/auth';
import React from 'react';

/**
 * Site admin only (same as parent account layout).
 * Keeps LLM / cloud credential UI aligned with backend get_admin_user even if routes move.
 */
export default async function AccountDevelopmentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions);
  if (!session) {
    redirect('/');
  }
  if (session.user?.role !== 'admin') {
    redirect('/settings');
  }
  return <>{children}</>;
}
