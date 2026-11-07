'use client';

import React from 'react';

import { AuthLayoutGuard } from '@/components/AuthLayoutGuard';

export default function AccountDevelopmentLayout({ children }: { children: React.ReactNode }) {
  return <AuthLayoutGuard requireSysAdmin>{children}</AuthLayoutGuard>;
}
