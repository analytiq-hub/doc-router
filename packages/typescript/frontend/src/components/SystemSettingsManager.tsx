import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { SystemSettings, SystemSettingsUpdate } from '@docrouter/sdk';
import { DocRouterAccountApi } from '@/utils/api';
import { getApiErrorMsg } from '@/utils/api';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';

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
    llm_max_concurrent_by_model: {},
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

    const payload: SystemSettingsUpdate = {
      textract_max_concurrent: clampTextractMaxConcurrent(settings.textract_max_concurrent),
      n_ocr_workers: clampWorkerCount(settings.n_ocr_workers),
      n_llm_workers: clampWorkerCount(settings.n_llm_workers),
      n_kb_index_workers: clampWorkerCount(settings.n_kb_index_workers),
      n_webhook_workers: clampWorkerCount(settings.n_webhook_workers),
      n_flow_run_workers: clampWorkerCount(settings.n_flow_run_workers),
    };
    setSettings((prev) => ({ ...prev, ...payload }));

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
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">OCR concurrency</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-sm text-muted-foreground">
            Limits how many Textract jobs each queue-worker pod runs at once. Set to 0 to disable the
            limit. This applies per worker pod, not cluster-wide.
          </p>

          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <Field className="max-w-xs">
              <FieldLabel htmlFor="textract-max-concurrent">Max concurrent Textract jobs</FieldLabel>
              <Input
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
              />
              <FieldDescription>
                Range {MIN_TEXTRACT_MAX_CONCURRENT}–{MAX_TEXTRACT_MAX_CONCURRENT} (default{' '}
                {DEFAULT_TEXTRACT_MAX_CONCURRENT}).
              </FieldDescription>
            </Field>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Queue worker counts</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-sm text-muted-foreground">
            Number of asyncio consumers per queue type in each queue-worker process. Counts resize
            automatically without a restart. Idle workers are removed immediately; busy workers finish
            their current job before exiting. Set all to 0 to stop queue processing on this pod.
          </p>

          {!loading ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {WORKER_COUNT_FIELDS.map(({ field, label }) => (
                  <Field key={field}>
                    <FieldLabel htmlFor={field}>{label}</FieldLabel>
                    <Input
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
                    />
                  </Field>
                ))}
              </div>

              <FieldDescription className="mt-3">
                Range {MIN_WORKER_COUNT}–{MAX_WORKER_COUNT} per queue (default {DEFAULT_WORKER_COUNT} each).
              </FieldDescription>

              {settings.updated_at ? (
                <p className="mt-3 text-xs text-muted-foreground">
                  Last updated: {new Date(settings.updated_at).toLocaleString()}
                </p>
              ) : null}

              <Button type="button" className="mt-4" onClick={() => void handleSave()} disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </Button>
            </>
          ) : null}

          {error ? (
            <Alert variant="destructive" className="mt-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          {success ? (
            <Alert variant="success" className="mt-4">
              <AlertDescription>{success}</AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
};

export default SystemSettingsManager;
