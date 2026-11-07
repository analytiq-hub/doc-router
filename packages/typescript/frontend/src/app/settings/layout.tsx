'use client';

import React from 'react';

import { AuthLayoutGuard } from '@/components/AuthLayoutGuard';

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return <AuthLayoutGuard>{children}</AuthLayoutGuard>;
}
