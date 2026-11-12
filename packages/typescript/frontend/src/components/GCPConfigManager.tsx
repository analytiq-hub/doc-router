import React, { useState, useEffect, useMemo, useCallback } from 'react';
import type { GCPConfig } from '@docrouter/sdk';
import { DocRouterAccountApi } from '@/utils/api';
import { getApiErrorMsg } from '@/utils/api';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { FormDialog } from '@/components/FormDialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldLabel } from '@/components/ui/field';
import { Textarea } from '@/components/ui/textarea';

const GCPConfigManager: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [gcpConfig, setGcpConfig] = useState<GCPConfig | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [jsonText, setJsonText] = useState('');
  const [fileName, setFileName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const cfg = await docRouterAccountApi.getGCPConfig();
      setGcpConfig(cfg);
      setConfigured(true);
    } catch {
      setGcpConfig(null);
      setConfigured(false);
    }
  }, [docRouterAccountApi]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const cfg = await docRouterAccountApi.getGCPConfig();
        if (!cancelled) {
          setGcpConfig(cfg);
          setConfigured(true);
        }
      } catch {
        if (!cancelled) {
          setGcpConfig(null);
          setConfigured(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [docRouterAccountApi]);

  const handleSave = async () => {
    setError(null);
    const raw = jsonText.trim();
    if (!raw) {
      setError('Paste or upload a service account JSON file.');
      return;
    }
    try {
      JSON.parse(raw);
    } catch {
      setError('Invalid JSON.');
      return;
    }
    try {
      await docRouterAccountApi.createGCPConfig({ service_account_json: raw });
      setEditOpen(false);
      setJsonText('');
      setFileName('');
      await refresh();
    } catch (e: unknown) {
      setError(getApiErrorMsg(e) || 'Failed to save GCP configuration.');
    }
  };

  const handleDelete = async () => {
    setError(null);
    try {
      await docRouterAccountApi.deleteGCPConfig();
      setDeleteOpen(false);
      await refresh();
    } catch (e: unknown) {
      setError(getApiErrorMsg(e) || 'Failed to delete GCP configuration.');
    }
  };

  const openEdit = () => {
    setEditOpen(true);
    setJsonText('');
    setFileName('');
    setError(null);
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0">
          <CardTitle className="text-lg">GCP (Vertex AI)</CardTitle>
          <Button type="button" onClick={openEdit}>
            {configured ? 'Edit JSON key' : 'Add JSON key'}
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Service account JSON used for Vertex AI models. The service account must be granted the{' '}
            <b>Vertex AI User</b> role (<code>roles/aiplatform.user</code>) on the project, and the Vertex AI API
            must be enabled.
          </p>
          <p className="text-sm">
            <b>Status:</b>{' '}
            {configured === null ? (
              <span className="text-muted-foreground">Loading…</span>
            ) : configured ? (
              <span className="text-green-600">Configured</span>
            ) : (
              <span className="text-amber-600">Not configured</span>
            )}
          </p>
          {configured && gcpConfig ? (
            <div className="mt-4 space-y-1 font-mono text-sm text-foreground">
              <div className="break-all">
                <span className="text-muted-foreground">Project ID:</span> {gcpConfig.project_id || '—'}
              </div>
              <div className="break-all">
                <span className="text-muted-foreground">Service account:</span> {gcpConfig.client_email || '—'}
              </div>
              <div className="break-all">
                <span className="text-muted-foreground">Client ID:</span> {gcpConfig.client_id || '—'}
              </div>
              <div className="break-all">
                <span className="text-muted-foreground">Private key ID:</span> {gcpConfig.private_key_id || '—'}
              </div>
            </div>
          ) : null}
          {configured ? (
            <Button type="button" variant="outline" className="mt-2 text-destructive" onClick={() => setDeleteOpen(true)}>
              Remove GCP key
            </Button>
          ) : null}
          {error && !editOpen ? (
            <Alert variant="destructive" className="mt-3">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <Card className="border-primary/30 bg-primary-soft">
        <CardContent className="pt-6 text-sm text-foreground">
          Change GCP configuration for on-prem installs only.
        </CardContent>
      </Card>

      {editOpen ? (
        <FormDialog
          title="GCP service account JSON"
          submitLabel="Save"
          submitDisabled={!jsonText.trim()}
          error={error}
          size="wide"
          onSubmit={() => void handleSave()}
          onClose={() => {
            setEditOpen(false);
            setError(null);
          }}
        >
          <Field>
            <FieldLabel>Service account JSON</FieldLabel>
            <label className="mb-2 inline-block cursor-pointer text-sm text-primary hover:underline">
              Choose JSON file
              <input
                type="file"
                accept=".json,application/json"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  setFileName(file.name);
                  const reader = new FileReader();
                  reader.onload = (ev) => {
                    const text = ev.target?.result as string;
                    setJsonText(text);
                    setError(null);
                  };
                  reader.readAsText(file);
                }}
              />
            </label>
            {fileName ? <span className="ml-2 text-sm text-muted-foreground">{fileName}</span> : null}
            <Textarea
              className="mt-2 min-h-48 font-mono text-xs"
              placeholder="Paste service account JSON…"
              value={jsonText}
              onChange={(e) => {
                setJsonText(e.target.value);
                setError(null);
              }}
            />
          </Field>
        </FormDialog>
      ) : null}

      <ConfirmDialog
        open={deleteOpen}
        title="Remove GCP key"
        message="Remove the stored GCP service account JSON? Vertex AI features that depend on it may stop working."
        confirmLabel="Remove"
        onConfirm={() => void handleDelete()}
        onClose={() => setDeleteOpen(false)}
      />
    </div>
  );
};

export default GCPConfigManager;
