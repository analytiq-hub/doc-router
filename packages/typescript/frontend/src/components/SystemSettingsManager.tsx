import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { DocRouterAccountApi } from '@/utils/api';
import { getApiErrorMsg } from '@/utils/api';

const MIN_TEXTRACT_MAX_CONCURRENT = 0;
const MAX_TEXTRACT_MAX_CONCURRENT = 1024;
const DEFAULT_TEXTRACT_MAX_CONCURRENT = 32;

function clampTextractMaxConcurrent(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_TEXTRACT_MAX_CONCURRENT;
  return Math.min(
    MAX_TEXTRACT_MAX_CONCURRENT,
    Math.max(MIN_TEXTRACT_MAX_CONCURRENT, Math.trunc(value)),
  );
}

const SystemSettingsManager: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [textractMaxConcurrent, setTextractMaxConcurrent] = useState(DEFAULT_TEXTRACT_MAX_CONCURRENT);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const settings = await docRouterAccountApi.getSystemSettings();
      setTextractMaxConcurrent(settings.textract_max_concurrent);
      setUpdatedAt(settings.updated_at ?? null);
    } catch (err) {
      setError(getApiErrorMsg(err) || 'Failed to load system settings.');
    } finally {
      setLoading(false);
    }
  }, [docRouterAccountApi]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    const value = clampTextractMaxConcurrent(textractMaxConcurrent);
    setTextractMaxConcurrent(value);
    try {
      const settings = await docRouterAccountApi.updateSystemSettings({
        textract_max_concurrent: value,
      });
      setTextractMaxConcurrent(settings.textract_max_concurrent);
      setUpdatedAt(settings.updated_at ?? null);
      setSuccess('Worker settings saved. Queue workers pick up changes within about 25 OCR jobs.');
    } catch (err) {
      setError(getApiErrorMsg(err) || 'Failed to save system settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-medium text-gray-900 mb-2">OCR concurrency</h2>
        <p className="text-sm text-gray-600 mb-4">
          Limits how many Textract jobs each queue-worker pod runs at once. Set to 0 to disable the
          limit. This applies per worker pod, not cluster-wide.
        </p>

        {loading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : (
          <div className="max-w-xs space-y-3">
            <div>
              <label
                htmlFor="textract-max-concurrent"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Max concurrent Textract jobs
              </label>
              <input
                id="textract-max-concurrent"
                type="number"
                min={MIN_TEXTRACT_MAX_CONCURRENT}
                max={MAX_TEXTRACT_MAX_CONCURRENT}
                value={Number.isFinite(textractMaxConcurrent) ? textractMaxConcurrent : ''}
                onChange={(e) => setTextractMaxConcurrent(e.target.valueAsNumber)}
                disabled={saving}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              />
              <p className="text-xs text-gray-500 mt-1">
                Range {MIN_TEXTRACT_MAX_CONCURRENT}–{MAX_TEXTRACT_MAX_CONCURRENT} (default{' '}
                {DEFAULT_TEXTRACT_MAX_CONCURRENT}).
              </p>
            </div>

            {updatedAt && (
              <p className="text-xs text-gray-500">
                Last updated: {new Date(updatedAt).toLocaleString()}
              </p>
            )}

            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-blue-300"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        )}

        {error && <p className="text-sm text-red-600 mt-3">{error}</p>}
        {success && <p className="text-sm text-green-700 mt-3">{success}</p>}
      </div>
    </div>
  );
};

export default SystemSettingsManager;
