import { redirect } from 'next/navigation';
import { getAppServerSession } from '@/utils/session';
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
  const session = await getAppServerSession();
  if (!session) {
    redirect('/');
  }
  if (!session.user.isSysadmin) {
    redirect('/settings');
  }
  return <>{children}</>;
}
