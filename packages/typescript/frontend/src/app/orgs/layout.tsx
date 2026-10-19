import { redirect } from 'next/navigation';
import { getAppServerSession } from '@/utils/session';
import React from 'react';

export default async function OrgsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getAppServerSession();

  // Redirect to home if not authenticated
  if (!session) {
    redirect('/');
  }

  return <>{children}</>;
}
