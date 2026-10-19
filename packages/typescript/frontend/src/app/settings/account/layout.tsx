import { redirect } from 'next/navigation';
import { getAppServerSession } from '@/utils/session';
import React from 'react';

export default async function AccountSettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getAppServerSession();

  // Redirect to home if not authenticated
  if (!session) {
    redirect('/');
  }

  // Redirect to settings if not admin
  if (!session.user.isSysadmin) {
    redirect('/settings');
  }

  return <>{children}</>;
}
