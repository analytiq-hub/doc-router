'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import type { LicenseStatus } from '@docrouter/sdk';
import { useAppSession } from '@/contexts/AppSessionContext';
import { DocRouterAccountApi } from '@/utils/api';

const POLL_MS = 5 * 60 * 1000;

function bannerCopy(status: LicenseStatus, isAdmin: boolean): {
  tone: 'warning' | 'danger';
  title: string;
  detail: string;
} | null {
  if (status.mode === 'grace' || status.in_grace) {
    return {
      tone: 'warning',
      title: 'License grace period',
      detail:
        'Your product license has expired and is in its grace period. Renew soon to avoid losing access.',
    };
  }
  if (status.mode === 'expired') {
    return {
      tone: 'danger',
      title: 'License expired',
      detail: isAdmin
        ? 'Most of the product API is disabled. Update the license to restore access.'
        : 'Most of the product is unavailable. Contact your administrator.',
    };
  }
  if (status.mode === 'invalid') {
    return {
      tone: 'danger',
      title: 'License invalid',
      detail: isAdmin
        ? 'The installed license could not be verified. Update the license to restore access.'
        : 'The product license is invalid. Contact your administrator.',
    };
  }
  return null;
}

/**
 * Full-width header banner when the deployment license is in grace, expired, or invalid.
 */
const LicenseBanner: React.FC = () => {
  const { session, status: authStatus } = useAppSession();
  const api = useMemo(() => new DocRouterAccountApi(), []);
  const [license, setLicense] = useState<LicenseStatus | null>(null);

  const load = useCallback(async () => {
    if (authStatus !== 'authenticated') {
      setLicense(null);
      return;
    }
    try {
      const status = await api.getLicenseStatus();
      setLicense(status);
    } catch {
      // Don't block the shell if status is unreachable
      setLicense(null);
    }
  }, [api, authStatus]);

  useEffect(() => {
    void load();
    if (authStatus !== 'authenticated') return;
    const id = window.setInterval(() => void load(), POLL_MS);
    return () => window.clearInterval(id);
  }, [authStatus, load]);

  if (authStatus !== 'authenticated' || !license) return null;

  const isAdmin = session?.user?.role === 'admin';
  const copy = bannerCopy(license, isAdmin);
  if (!copy) return null;

  const toneClass =
    copy.tone === 'danger'
      ? 'bg-red-700 text-white'
      : 'bg-amber-500 text-gray-900';

  const linkClass =
    copy.tone === 'danger'
      ? 'underline font-semibold text-white'
      : 'underline font-semibold text-gray-900';

  return (
    <div
      role="status"
      className={`${toneClass} px-3 py-2 text-sm text-center`}
    >
      <span className="font-semibold">{copy.title}.</span>{' '}
      <span>{copy.detail}</span>
      {isAdmin ? (
        <>
          {' '}
          <Link href="/settings/account/license" className={linkClass}>
            Open License settings
          </Link>
        </>
      ) : null}
    </div>
  );
};

export default LicenseBanner;
