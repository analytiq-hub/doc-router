'use client';

import React from 'react';

import { AuthLayoutGuard } from '@/components/AuthLayoutGuard';

export default function OrgsLayout({ children }: { children: React.ReactNode }) {
  return <AuthLayoutGuard>{children}</AuthLayoutGuard>;
}
