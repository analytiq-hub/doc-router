import { redirect } from 'next/navigation';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/auth';
import React from 'react';

export default async function AccountSettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions);

  // Redirect to home if not authenticated
  if (!session) {
    redirect('/');
  }

  // Redirect to settings if not admin
  if (session.user?.role !== 'admin') {
    redirect('/settings');
  }

  return <>{children}</>;
}
