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

export type SystemSettingsSection = 'queues' | 'limits';

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

function limitsDirty(current: SystemSettings, baseline: SystemSettings): boolean {
  const draft = Number.isFinite(current.textract_max_concurrent)
    ? clampTextractMaxConcurrent(current.textract_max_concurrent)
    : null;
  if (draft === null) return true;
  return draft !== clampTextractMaxConcurrent(baseline.textract_max_concurrent);
}

function queuesDirty(current: SystemSettings, baseline: SystemSettings): boolean {
  return WORKER_COUNT_FIELDS.some(({ field }) => {
    const draft = Number.isFinite(current[field]) ? clampWorkerCount(current[field]) : null;
    if (draft === null) return true;
    return draft !== clampWorkerCount(baseline[field]);
  });
}

const SystemSettingsManager: React.FC<{ section: SystemSettingsSection }> = ({ section }) => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [settings, setSettings] = useState<SystemSettings>(defaultSettings);
  const [savedSettings, setSavedSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDirty = useMemo(() => {
    if (!savedSettings || loading) return false;
    return section === 'limits'
      ? limitsDirty(settings, savedSettings)
      : queuesDirty(settings, savedSettings);
  }, [loading, savedSettings, section, settings]);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await docRouterAccountApi.getSystemSettings();
      setSettings(loaded);
      setSavedSettings(loaded);
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

    const payload: SystemSettingsUpdate =
      section === 'limits'
        ? {
            textract_max_concurrent: clampTextractMaxConcurrent(settings.textract_max_concurrent),
          }
        : {
            n_ocr_workers: clampWorkerCount(settings.n_ocr_workers),
            n_llm_workers: clampWorkerCount(settings.n_llm_workers),
            n_kb_index_workers: clampWorkerCount(settings.n_kb_index_workers),
            n_webhook_workers: clampWorkerCount(settings.n_webhook_workers),
            n_flow_run_workers: clampWorkerCount(settings.n_flow_run_workers),
          };

    try {
      const saved = await docRouterAccountApi.updateSystemSettings(payload);
      setSettings(saved);
      setSavedSettings(saved);
    } catch (err) {
      setError(getApiErrorMsg(err) || 'Failed to save system settings.');
    } finally {
      setSaving(false);
    }
  };

  const saveButton = (
    <Button
      type="button"
      className="mt-4 w-fit self-start"
      onClick={() => void handleSave()}
      disabled={saving || loading || !isDirty}
    >
      {saving ? 'Saving…' : 'Save'}
    </Button>
  );

  const errorAlert = error ? (
    <Alert variant="destructive" className="mt-4">
      <AlertDescription>{error}</AlertDescription>
    </Alert>
  ) : null;

  if (section === 'limits') {
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">OCR (Textract)</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-4 text-sm text-muted-foreground">
              Limits how many Textract jobs each queue-worker pod runs at once. Set to 0 to disable the
              limit. This applies per worker pod, not cluster-wide.
            </p>
            <p className="mb-4 text-sm text-muted-foreground">
              Per-model LLM concurrency limits are configured on the LLM models table in Development
              settings.
            </p>

            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : (
              <FieldGroup>
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
                {saveButton}
                {errorAlert}
              </FieldGroup>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
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

          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
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

              {saveButton}
              {errorAlert}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default SystemSettingsManager;