'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { LicenseAdminView } from '@docrouter/sdk';
import { DocRouterAccountApi, getApiErrorMsg } from '@/utils/api';
import SettingsLayout, {
  settingsDescriptionClass,
  settingsPageTitleClass,
} from '@/components/SettingsLayout';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field';
import { Textarea } from '@/components/ui/textarea';

/** Parse API datetimes; timezone-less values are treated as UTC. */
function parseApiDate(value: string): Date | null {
  const raw = value.trim();
  const hasTz = /([zZ]|[+-]\d{2}:?\d{2})$/.test(raw);
  const iso = hasTz ? raw : `${raw}Z`;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Format last-checked etc. in the browser's local timezone. */
function formatLocalDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = parseApiDate(value);
  if (!date) return value;
  return date.toLocaleString(undefined, {
    dateStyle: 'short',
    timeStyle: 'medium',
  });
}

/**
 * Format license start/expiry as the UTC calendar date so it matches the
 * date entered when generating (stored as midnight UTC on that day).
 */
function formatLicenseCalendarDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = parseApiDate(value);
  if (!date) return value;
  return date.toLocaleDateString(undefined, {
    timeZone: 'UTC',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  });
}

const LicensePage: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [license, setLicense] = useState<LicenseAdminView | null>(null);
  const [licenseKey, setLicenseKey] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadLicense = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await docRouterAccountApi.getLicense();
      setLicense(loaded);
    } catch (err) {
      setError(getApiErrorMsg(err) || 'Failed to load license.');
    } finally {
      setLoading(false);
    }
  }, [docRouterAccountApi]);

  useEffect(() => {
    void loadLicense();
  }, [loadLicense]);

  const handleSave = async () => {
    const trimmed = licenseKey.trim();
    if (!trimmed) {
      setError('Paste a license key before saving.');
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await docRouterAccountApi.updateLicense(trimmed);
      setLicense(updated);
      setLicenseKey('');
      setSuccess('License updated.');
    } catch (err) {
      setError(getApiErrorMsg(err) || 'Failed to update license.');
    } finally {
      setSaving(false);
    }
  };

  const copyInstallationId = async () => {
    if (!license?.installation_id) return;
    try {
      await navigator.clipboard.writeText(license.installation_id);
      setSuccess('Installation ID copied.');
    } catch {
      setError('Could not copy installation ID.');
    }
  };

  return (
    <SettingsLayout selectedMenu="system_license">
      <div className="max-w-2xl space-y-6">
        <div>
          <h1 className={settingsPageTitleClass}>License</h1>
          <p className={`${settingsDescriptionClass} mt-1`}>
            View and replace the product license for this deployment.
          </p>
        </div>

        {loading && <p className="text-sm text-muted-foreground">Loading…</p>}

        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        {success ? (
          <Alert variant="success">
            <AlertDescription>{success}</AlertDescription>
          </Alert>
        ) : null}

        {license && !loading && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Current license</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
            <div className="grid grid-cols-[8rem_1fr] gap-y-2">
              <span className="text-gray-500">Status</span>
              <span className="font-medium text-gray-900">
                {license.mode}
                {license.valid ? '' : license.code ? ` (${license.code})` : ''}
              </span>
              <span className="text-gray-500">Customer</span>
              <span>{license.customer_name || '—'}</span>
              <span className="text-gray-500">Start</span>
              <span>{formatLicenseCalendarDate(license.not_before)}</span>
              <span className="text-gray-500">Expires</span>
              <span>
                {formatLicenseCalendarDate(license.expires_at)}
                {license.days_remaining != null
                  ? ` (${license.days_remaining} days remaining)`
                  : ''}
                {license.in_grace ? ' · in grace' : ''}
              </span>
              <span className="text-gray-500">Features</span>
              <span>
                {license.features?.length ? license.features.join(', ') : '—'}
              </span>
              <span className="text-gray-500">Limits</span>
              <span>
                {license.limits && Object.keys(license.limits).length
                  ? JSON.stringify(license.limits)
                  : '—'}
              </span>
              <span className="text-gray-500">Key</span>
              <span className="font-mono text-xs">{license.masked_key || '—'}</span>
              <span className="text-gray-500">Installation ID</span>
              <span className="flex items-center gap-2">
                <code className="font-mono text-xs">{license.installation_id || '—'}</code>
                {license.installation_id ? (
                  <Button type="button" variant="link" size="sm" className="h-auto px-0 text-xs" onClick={() => void copyInstallationId()}>
                    Copy
                  </Button>
                ) : null}
              </span>
              <span className="text-gray-500">Last checked</span>
              <span>{formatLocalDateTime(license.checked_at)}</span>
            </div>
            {license.message ? <p className="text-muted-foreground">{license.message}</p> : null}
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Update license</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
          <FieldDescription className={settingsDescriptionClass}>
            Paste a new signed license key. The previous key is kept if the new one is invalid.
          </FieldDescription>
          <Field>
            <FieldLabel htmlFor="license-key">License key</FieldLabel>
            <Textarea
              id="license-key"
              className="font-mono text-xs"
              rows={4}
              value={licenseKey}
              onChange={(e) => setLicenseKey(e.target.value)}
              placeholder="DRLIC1.…"
              spellCheck={false}
            />
          </Field>
          <Button type="button" onClick={() => void handleSave()} disabled={saving}>
            {saving ? 'Saving…' : 'Save license'}
          </Button>
          </CardContent>
        </Card>
      </div>
    </SettingsLayout>
  );
};

export default LicensePage;
