import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { SystemSettings } from '@docrouter/sdk';
import { DocRouterAccountApi } from '@/utils/api';
import { getApiErrorMsg } from '@/utils/api';

const MIN_TEXTRACT_MAX_CONCURRENT = 0;
const MAX_TEXTRACT_MAX_CONCURRENT = 1024;
const DEFAULT_TEXTRACT_MAX_CONCURRENT = 32;

const MIN_WORKER_COUNT = 0;
const MAX_WORKER_COUNT = 256;
const DEFAULT_WORKER_COUNT = 4;

type WorkerCountField =
  | 'n_ocr_workers'
  | 'n_llm_workers'
  | 'n_kb_index_workers'
  | 'n_webhook_workers'
  | 'n_flow_run_workers';

const WORKER_COUNT_FIELDS: Array<{ field: WorkerCountField; label: string }> = [
  { field: 'n_ocr_workers', label: 'OCR queue workers' },
  { field: 'n_llm_workers', label: 'LLM queue workers' },
  { field: 'n_kb_index_workers', label: 'KB index queue workers' },
  { field: 'n_webhook_workers', label: 'Webhook queue workers' },
  { field: 'n_flow_run_workers', label: 'Flow run queue workers' },
];

function clampTextractMaxConcurrent(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_TEXTRACT_MAX_CONCURRENT;
  return Math.min(
    MAX_TEXTRACT_MAX_CONCURRENT,
    Math.max(MIN_TEXTRACT_MAX_CONCURRENT, Math.trunc(value)),
  );
}

function clampWorkerCount(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_WORKER_COUNT;
  return Math.min(MAX_WORKER_COUNT, Math.max(MIN_WORKER_COUNT, Math.trunc(value)));
}

function defaultSettings(): SystemSettings {
  return {
    textract_max_concurrent: DEFAULT_TEXTRACT_MAX_CONCURRENT,
    n_ocr_workers: DEFAULT_WORKER_COUNT,
    n_llm_workers: DEFAULT_WORKER_COUNT,
    n_kb_index_workers: DEFAULT_WORKER_COUNT,
    n_webhook_workers: DEFAULT_WORKER_COUNT,
    n_flow_run_workers: DEFAULT_WORKER_COUNT,
  };
}

const SystemSettingsManager: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [settings, setSettings] = useState<SystemSettings>(defaultSettings);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await docRouterAccountApi.getSystemSettings();
      setSettings(loaded);
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

    const payload: SystemSettings = {
      textract_max_concurrent: clampTextractMaxConcurrent(settings.textract_max_concurrent),
      n_ocr_workers: clampWorkerCount(settings.n_ocr_workers),
      n_llm_workers: clampWorkerCount(settings.n_llm_workers),
      n_kb_index_workers: clampWorkerCount(settings.n_kb_index_workers),
      n_webhook_workers: clampWorkerCount(settings.n_webhook_workers),
      n_flow_run_workers: clampWorkerCount(settings.n_flow_run_workers),
    };
    setSettings(payload);

    try {
      const saved = await docRouterAccountApi.updateSystemSettings(payload);
      setSettings(saved);
      setSuccess(
        'Worker settings saved. Textract limits refresh within about 25 jobs; queue worker counts resize within about 15 seconds.',
      );
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
                value={Number.isFinite(settings.textract_max_concurrent) ? settings.textract_max_concurrent : ''}
                onChange={(e) =>
                  setSettings((prev) => ({
                    ...prev,
                    textract_max_concurrent: e.target.valueAsNumber,
                  }))
                }
                disabled={saving}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              />
              <p className="text-xs text-gray-500 mt-1">
                Range {MIN_TEXTRACT_MAX_CONCURRENT}–{MAX_TEXTRACT_MAX_CONCURRENT} (default{' '}
                {DEFAULT_TEXTRACT_MAX_CONCURRENT}).
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-medium text-gray-900 mb-2">Queue worker counts</h2>
        <p className="text-sm text-gray-600 mb-4">
          Number of asyncio consumers per queue type in each queue-worker process. Counts resize
          automatically without a restart. Idle workers are removed immediately; busy workers finish
          their current job before exiting. Set all to 0 to stop queue processing on this pod.
        </p>

        {!loading && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {WORKER_COUNT_FIELDS.map(({ field, label }) => (
              <div key={field}>
                <label htmlFor={field} className="block text-sm font-medium text-gray-700 mb-1">
                  {label}
                </label>
                <input
                  id={field}
                  type="number"
                  min={MIN_WORKER_COUNT}
                  max={MAX_WORKER_COUNT}
                  value={Number.isFinite(settings[field]) ? settings[field] : ''}
                  onChange={(e) =>
                    setSettings((prev) => ({
                      ...prev,
                      [field]: e.target.valueAsNumber,
                    }))
                  }
                  disabled={saving}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                />
              </div>
            ))}
          </div>
        )}

        {!loading && (
          <p className="text-xs text-gray-500 mt-3">
            Range {MIN_WORKER_COUNT}–{MAX_WORKER_COUNT} per queue (default {DEFAULT_WORKER_COUNT} each).
          </p>
        )}

        {!loading && settings.updated_at && (
          <p className="text-xs text-gray-500 mt-3">
            Last updated: {new Date(settings.updated_at).toLocaleString()}
          </p>
        )}

        {!loading && (
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="mt-4 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-blue-300"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        )}

        {error && <p className="text-sm text-red-600 mt-3">{error}</p>}
        {success && <p className="text-sm text-green-700 mt-3">{success}</p>}
      </div>
    </div>
  );
};

export default SystemSettingsManager;
