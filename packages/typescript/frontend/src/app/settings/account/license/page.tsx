'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { LicenseAdminView } from '@docrouter/sdk';
import { DocRouterAccountApi, getApiErrorMsg } from '@/utils/api';
import SettingsLayout, {
  settingsDescriptionClass,
  settingsPageTitleClass,
} from '@/components/SettingsLayout';

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

        {loading && <p className="text-sm text-gray-600">Loading…</p>}

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">
            {success}
          </div>
        )}

        {license && !loading && (
          <div className="space-y-3 rounded-md border border-gray-200 bg-white p-4 text-sm">
            <div className="grid grid-cols-[8rem_1fr] gap-y-2">
              <span className="text-gray-500">Status</span>
              <span className="font-medium text-gray-900">
                {license.mode}
                {license.valid ? '' : license.code ? ` (${license.code})` : ''}
              </span>
              <span className="text-gray-500">Customer</span>
              <span>{license.customer_name || '—'}</span>
              <span className="text-gray-500">Expires</span>
              <span>
                {license.expires_at
                  ? new Date(license.expires_at).toLocaleString()
                  : '—'}
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
                {license.installation_id && (
                  <button
                    type="button"
                    onClick={() => void copyInstallationId()}
                    className="text-xs text-blue-700 hover:underline"
                  >
                    Copy
                  </button>
                )}
              </span>
              <span className="text-gray-500">Last checked</span>
              <span>
                {license.checked_at
                  ? new Date(license.checked_at).toLocaleString()
                  : '—'}
              </span>
            </div>
            {license.message && (
              <p className="text-gray-600">{license.message}</p>
            )}
          </div>
        )}

        <div className="space-y-3">
          <h2 className="text-base font-semibold text-gray-900">Update license</h2>
          <p className={settingsDescriptionClass}>
            Paste a new signed license key. The previous key is kept if the new
            one is invalid.
          </p>
          <textarea
            className="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-xs"
            rows={4}
            value={licenseKey}
            onChange={(e) => setLicenseKey(e.target.value)}
            placeholder="DRLIC1.…"
            spellCheck={false}
          />
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save license'}
          </button>
        </div>
      </div>
    </SettingsLayout>
  );
};

export default LicensePage;
